import requests

url = "https://api.gdeltproject.org/api/v2/doc/doc?query=technology&mode=artlist&format=json&timespan=1h"

response = requests.get(url)

print(response.status_code)
print(response.json())
