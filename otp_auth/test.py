
import os

from telesign.messaging import MessagingClient
customer_id = os.getenv('CUSTOMER_ID', 'C61A30CB-CCEE-48F0-A196-B9A60C72B642')
api_key = os.getenv('API_KEY', 'vd5hZoJhqrG2ioRGreiTh8BHNa70+jeBe8V+07szZ+FKK8yeQ9PGT1G1dhsKfG1ZUHZlyKYMGBnj/q7NBPDbdw==')
phone_number = os.getenv('PHONE_NUMBER', '916383235832')

message = "Get 50% off your next order with our holiday offer. See details here: https://vero-finto.com/holiday-offer42 Reply STOP to opt out"
message_type = "ARN"

messaging = MessagingClient(customer_id, api_key)

# Make the request and capture the response.
response = messaging.message(phone_number, message, message_type)

# Display the response body in the console for debugging purposes.
# In your production code, you would likely remove this.
print(f"\nResponse:\n{response.body}\n")