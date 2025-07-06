import requests

url = "https://www.dataextractorapi.com/api/extract"
data = {
    "text": "John Doe lives at 123 Main St, NYC, phone: (555) 123-4567",
    "fields": "name,address,phone"

}

response = requests.post(url, json=data)
result = response.json()
print(result)
