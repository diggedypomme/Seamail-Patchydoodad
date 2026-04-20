from neo4j import GraphDatabase
import json

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "seaman123"))

def find_creature_pointers():
    with driver.session(database="seaman") as session:
        # Search for functions that handle "Seaman" and global pointers (DAT_)
        q = """
        MATCH (n:Function) 
        WHERE (n.summary CONTAINS 'Seaman' OR n.summary CONTAINS 'creature' OR n.summary CONTAINS 'CHigyo')
          AND n.summary CONTAINS 'DAT_'
        RETURN n.name as name, n.summary as summary
        """
        res = session.run(q)
        return [dict(r) for r in res]

findings = find_creature_pointers()
with open("creature_pointer_investigation.json", "w") as f:
    json.dump(findings, f, indent=2)

print(f"Found {len(findings)} potential leads.")
driver.close()
