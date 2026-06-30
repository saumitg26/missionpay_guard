import boto3
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("missionpay-cases")
response = table.scan(ProjectionExpression="case_id")
for item in response.get("Items", []):
    table.delete_item(Key={"case_id": item["case_id"]})
    print("Deleted:", item["case_id"])
print("All cleaned")
