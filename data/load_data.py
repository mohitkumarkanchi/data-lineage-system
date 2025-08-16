import os
import json
from neo4j import GraphDatabase, basic_auth


class Neo4jDataLoader:
    def __init__(self, uri, user, password, database=None):
        """
        Initialize Neo4j driver
        :param uri: Bolt URI, e.g., bolt://localhost:7687
        :param user: Neo4j user, e.g., neo4j
        :param password: Neo4j password
        :param database: Database name (for multi-db support, default None for default DB)
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))

    def close(self):
        self.driver.close()

    def run_cypher(self, query, parameters=None):
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return result.data()

    def create_database(self, db_name):
        """
        Create a new database (only if supported)
        This requires admin privileges and Neo4j 4.x+
        """
        if not self.database == "system":
            print("Switching to system database to create new database...")
            with self.driver.session(database="system") as session:
                session.run(f"CREATE DATABASE {db_name} IF NOT EXISTS")
            print(f"Database '{db_name}' created or already exists.")
        else:
            print("Already connected to system database.")

    def create_constraints(self):
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FactCheck) REQUIRE f.id IS UNIQUE"
        ]
        print("Creating uniqueness constraints...")
        for cql in constraints:
            self.run_cypher(cql)
        print("Constraints created or verified.")

    def load_json_as_nodes(self, json_path, label, property_mapping):
        """
        Load JSON file contents and import as nodes.
        Uses UNWIND with parameters to reduce number of queries.
        :param json_path: Path to JSON file with list of dicts
        :param label: Neo4j node label, e.g., User, Post
        :param property_mapping: Dict mapping node property names to JSON keys or transformation code
        """
        print(f"Loading nodes from {json_path} as :{label}...")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Prepare list of dicts with properties per property_mapping
        nodes_to_create = []
        for entry in data:
            node_props = {}
            for prop, json_key in property_mapping.items():
                # Simple direct mapping or use a callable for transformation
                if callable(json_key):
                    try:
                        node_props[prop] = json_key(entry)
                    except Exception as e:
                        print(f"Error processing property {prop}: {e}")
                        node_props[prop] = None
                else:
                    node_props[prop] = entry.get(json_key)
            nodes_to_create.append(node_props)

        # Cypher: UNWIND parameter list to create nodes
        props_keys = list(property_mapping.keys())
        props_str = ", ".join([f"{k}: row.{k}" for k in props_keys])

        cypher = f"""
        UNWIND $batch as row
        MERGE (n:{label} {{id: row.id}})
        SET n += {{{props_str}}}
        """
        self.run_cypher(cypher, {"batch": nodes_to_create})
        print(f"Imported {len(nodes_to_create)} nodes as :{label}")

    def load_relationships(self, json_path):
        """
        Load relationships from JSON and create relations.
        Assumes JSON has: from, relationship, to
        """
        print(f"Loading relationships from {json_path}...")

        with open(json_path, "r", encoding="utf-8") as f:
            rels = json.load(f)

        rels_to_create = []
        valid_rel_types = {"CREATED", "VERIFIED_BY", "SHARED"}

        for r in rels:
            from_id = r.get("from")
            to_id = r.get("to")
            rel_type = r.get("relationship")

            if rel_type not in valid_rel_types:
                print(f"Skipping unknown relationship type: {rel_type}")
                continue

            rels_to_create.append({
                "from_id": from_id,
                "rel_type": rel_type,
                "to_id": to_id,
            })

        # Create relationships by type, ensure MATCH uses id property to find nodes
        for rel_type in valid_rel_types:
            batch = [r for r in rels_to_create if r["rel_type"] == rel_type]
            if not batch:
                continue

            cypher = f"""
            UNWIND $batch AS row
            MATCH (a {{id: row.from_id}}), (b {{id: row.to_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            """
            self.run_cypher(cypher, {"batch": batch})

        print(f"Imported {len(rels_to_create)} relationships.")

    def create_author_relationships(self):
        """
        Create explicit CREATED relationships from Posts' author_id to Users
        """
        print("Creating author-post relationships (CREATED) from author_id...")
        cypher = """
        MATCH (u:User), (p:Post)
        WHERE p.author_id = u.id
        MERGE (u)-[:CREATED]->(p)
        """
        self.run_cypher(cypher)
        print("Author-post relationships created.")


def main():
    # Configurations - change these to match your setup
    NEO4J_URI = "neo4j://127.0.0.1:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "tempInstance"
    DATABASE_NAME = "neo4j"  # e.g., "socialmedia" or None for default

    # Paths to your JSON files - adjust to actual path where your JSON files live
    DATA_DIR = "./data"
    USERS_JSON = os.path.join(DATA_DIR, "users.json")
    POSTS_JSON = os.path.join(DATA_DIR, "posts.json")
    FACTCHECKS_JSON = os.path.join(DATA_DIR, "factchecks.json")
    RELATIONSHIPS_JSON = os.path.join(DATA_DIR, "relationships.json")

    loader = Neo4jDataLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DATABASE_NAME)

    # Optional: create a new database (if your Neo4j supports multi-db)
    # loader.create_database("socialmedia")

    # Create uniqueness constraints
    loader.create_constraints()

    # Load nodes:
    loader.load_json_as_nodes(
        USERS_JSON,
        "User",
        {
            "id": "id",
            "name": "name",
            "username": "username",
            "email": "email",
            "followers": "followers",
            "account_created": lambda d: d.get("account_created"),
            "verified": "verified",
            "location": "location",
        },
    )

    loader.load_json_as_nodes(
        POSTS_JSON,
        "Post",
        {
            "id": "id",
            "content": "content",
            "timestamp": lambda d: d.get("timestamp"),
            "likes": "likes",
            "shares": "shares",
            "comments": "comments",
            "platform": "platform",
            "tags": "tags",
            "author_id": "author_id",
        },
    )

    loader.load_json_as_nodes(
        FACTCHECKS_JSON,
        "FactCheck",
        {
            "id": "id",
            "status": "status",
            "verified_at": lambda d: d.get("verified_at"),
            "comments": "comments",
            "source_url": "source_url",
        },
    )

    # Create author-post relationships from author_id property before loading other relations
    loader.create_author_relationships()

    # Load other relationships
    loader.load_relationships(RELATIONSHIPS_JSON)

    loader.close()
    print("Data loading completed successfully.")


if __name__ == "__main__":
    main()
