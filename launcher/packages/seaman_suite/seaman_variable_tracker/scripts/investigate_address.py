from neo4j import GraphDatabase
import json

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "seaman123"))

def investigate(addr):
    with driver.session(database="seaman") as session:
        clean_addr = addr.replace("0x", "DAT_")
        # Search for the address in function summaries
        q = f"MATCH (n:Function) WHERE n.summary CONTAINS '{clean_addr}' RETURN n.name as name, n.summary as summary"
        res = session.run(q)
        matches = [dict(r) for r in res]
        
        # Also search for the address itself in the name if it's a constant
        q2 = f"MATCH (n:Function) WHERE n.name CONTAINS '{clean_addr}' RETURN n.name as name, n.summary as summary"
        res2 = session.run(q2)
        matches.extend([dict(r) for r in res2])
        
        return matches

if __name__ == "__main__":
    target = "0x004602e8"
    results = investigate(target)
    print(f"Found {len(results)} matches for {target}:")
    for r in results:
        print(f"--- {r['name']} ---")
        print(r['summary'])
    
    with open("mystery_address_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    driver.close()
