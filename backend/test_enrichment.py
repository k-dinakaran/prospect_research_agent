from app.enrichment import enrich_company

if __name__ == "__main__":
    result = enrich_company("https://www.netaxis.in")
    print(result)