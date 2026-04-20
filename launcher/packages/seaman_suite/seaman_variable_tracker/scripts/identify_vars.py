from neo4j import GraphDatabase
import json

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "seaman123"))

def query_addresses(addresses):
    with driver.session(database="seaman") as session:
        results = {}
        for addr in addresses:
            # Address in JSON is 0x00452668, but in Neo4j summary it might be DAT_00452668
            clean_addr = addr.replace("0x", "DAT_")
            q = f"MATCH (n:Function) WHERE n.summary CONTAINS '{clean_addr}' RETURN n.name as name, n.summary as summary"
            res = session.run(q)
            results[addr] = [dict(r) for r in res]
        return results

# Addresses from the screenshot with interesting values
target_addresses = [
    "0x00452680", # 3.1416
    "0x00452678", # 33.3
    "0x00452670", # 1
    "0x00452664", # 0.5
    "0x00452668", # 0.03
    "0x004526ac", # Hunger rate
    "0x00468a30", # 'face' ID
    "0x00468b90", # Sound/Audio increasing
    "0x00468bbc", # Input/Interaction decreasing
    "0x0046906c", # Decreasing int
    "0x0046907c", # Increasing float (timer?)
    "0x00465098", # Float 1.4 -> 1.0
    "0x00469070", # Sync Big Hex
    "0x00469074", # Sync Big Hex
]

matches = query_addresses(target_addresses)
with open("address_identification_results.json", "w") as f:
    json.dump(matches, f, indent=2)

print(f"Identified {len(matches)} addresses. Check results.")
driver.close()
