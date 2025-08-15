// Import Users
CALL apoc.load.json("file:///users.json") YIELD value AS user
MERGE (u:User {id: user.id})
SET u.name = user.name,
    u.username = user.username,
    u.email = user.email,
    u.followers = user.followers,
    u.account_created = date(user.account_created),
    u.verified = user.verified,
    u.location = user.location;

// Import Posts
CALL apoc.load.json("file:///posts.json") YIELD value AS post
MERGE (p:Post {id: post.id})
SET p.content = post.content,
    p.timestamp = datetime(post.timestamp),
    p.likes = post.likes,
    p.shares = post.shares,
    p.comments = post.comments,
    p.platform = post.platform,
    p.tags = post.tags,
    p.shared_post_id = post.shared_post_id;

// Import FactChecks
CALL apoc.load.json("file:///factchecks.json") YIELD value AS fc
MERGE (f:FactCheck {id: fc.id})
SET f.status = fc.status,
    f.verified_at = datetime(fc.verified_at),
    f.comments = fc.comments,
    f.source_url = fc.source_url;

// Create relationships from relationships.json
CALL apoc.load.json("file:///relationships.json") YIELD value AS rel
MATCH (fromNode {id: rel.from}), (toNode {id: rel.to})
CALL apoc.do.when(
  rel.relationship = "CREATED",
  'MERGE (fromNode)-[:CREATED]->(toNode)',
  '',
  {fromNode: fromNode, toNode: toNode}
) YIELD value
CALL apoc.do.when(
  rel.relationship = "VERIFIED_BY",
  'MERGE (fromNode)-[:VERIFIED_BY]->(toNode)',
  '',
  {fromNode: fromNode, toNode: toNode}
) YIELD value
CALL apoc.do.when(
  rel.relationship = "SHARED",
  'MERGE (fromNode)-[:SHARED]->(toNode)',
  '',
  {fromNode: fromNode, toNode: toNode}
) YIELD value
RETURN "Import complete";
