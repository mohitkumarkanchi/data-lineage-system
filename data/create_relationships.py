import json

# Load users and posts data from disk
with open("data/users.json", "r") as f:
    users = json.load(f)

with open("data/posts.json", "r") as f:
    posts = json.load(f)

relationships = []

# Map user IDs to validate authors exist (optional but good)
user_ids = set(user["id"] for user in users)
post_ids = set(post["id"] for post in posts)

# 1) Create CREATED relationships: User -> Post
for post in posts:
    author_id = post.get("author_id")
    post_id = post["id"]
    if author_id in user_ids:
        relationships.append({
            "from": author_id,
            "relationship": "CREATED",
            "to": post_id
        })
    else:
        print(f"Warning: Post {post_id} references unknown author_id '{author_id}'")

# 2) Create SHARED relationships: Shared Post -> Original Post
# Using the 'shared_post_id' field if present
for post in posts:
    shared_post_id = post.get("shared_post_id")
    if shared_post_id:
        if shared_post_id in post_ids:
            relationships.append({
                "from": post["id"],
                "relationship": "SHARED",
                "to": shared_post_id
            })
        else:
            print(f"Warning: Post {post['id']} shares unknown post '{shared_post_id}'")

# (Optional) Add more relationships here if needed

# Write the relationships to the output JSON file
with open("data/relationships.json", "w") as f:
    json.dump(relationships, f, indent=2)

print(f"Generated relationships.json with {len(relationships)} relationships")
