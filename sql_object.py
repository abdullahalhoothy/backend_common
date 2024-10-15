from dataclasses import dataclass

@dataclass
class SqlObject:
    upsert_user_profile_query: str = """
        INSERT INTO user_data
        (user_id, prdcer_dataset, prdcer_lyrs, prdcer_ctlgs, draft_ctlgs)
            VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id) DO UPDATE
        SET prdcer_dataset = $2, 
            prdcer_lyrs = $3, 
            prdcer_ctlgs = $4, 
            draft_ctlgs = $5; 
    """
    load_user_profile_query: str = """SELECT * FROM user_data WHERE user_id = $1;"""


    upsert_customer_user_query: str = """
        INSERT INTO stripe_customers (user_id, customer_id) VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE
        SET customer_id = $2;
    """

    fetch_customer_id_by_user_id__stripe_query = "SELECT customer_id FROM stripe_customers WHERE user_id = $1"


    delete_customer_strip_query = """DELETE FROM stripe_customers WHERE customer_id = $1"""