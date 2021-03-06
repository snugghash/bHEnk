from google.cloud import bigquery
from pprint import pprint



def main():
    data = get_data_from_big_query(10)
    pprint(get_relevant_info_as_dict(data))



def get_data_from_big_query(number_of_rows):
    client = bigquery.Client.from_service_account_json(
        'scalable-homom-encryp-2e445d235e13.json',
        project='bigquery-public-data')

    reference = client.dataset('bitcoin_blockchain')
    dataset = client.get_dataset(reference)
    transactions_table_ref = client.get_table(dataset.table('transactions'))

    schema_subset = [
        col for col in transactions_table_ref.schema
        if col.name in ('inputs', 'outputs', 'transaction_id', 'timestamp')
    ]
    return [
        x for x in client.list_rows(
            transactions_table_ref,
            start_index=0,
            selected_fields=schema_subset,
            max_results=number_of_rows)
    ]



def get_relevant_info_as_dict(results):
    """
    Returns relevant info: inputs, outputs, etc. in dict, given dict
    """
    formatted = []
    for row in results:
        dict_row = dict(row)
        formatted_row = {}
        formatted_row['inputs'] = []
        for i in dict_row['inputs']:
            formatted_row['inputs'].append({'from': i['input_pubkey_base58']})
            # Note: BTC has no concept of addresses. ALL the amount from ALL addresses here is taken, then distributed as the outputs describe.
        formatted_row['outputs'] = []
        for i in dict_row['outputs']:
            formatted_row['outputs'].append({
                'to': i['output_pubkey_base58'],
                'amount': i['output_satoshis']
            })
        formatted_row['timestamp'] = dict_row['timestamp']
        formatted_row['id'] = dict_row['transaction_id']
        formatted.append(formatted_row)
    return formatted



if __name__ == "__main__":
    main()
