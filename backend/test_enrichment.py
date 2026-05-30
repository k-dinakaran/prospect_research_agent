from app.enrichment import enrich_company

if __name__ == "__main__":
    result = enrich_company("https://www.zoho.com")
    print(result)