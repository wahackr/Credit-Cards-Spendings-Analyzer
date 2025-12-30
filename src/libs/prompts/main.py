STATEMENT_READER_INSTUCTIONS = """
Analyze the credit card statments, list out all the transactions with date (YYYY-MM-DD), transaction name and amount. Payment credits can be ignored.
Some statments may incluing the original currency and amount, but please always use the HKD column for analysis.
Some statments may use more than 1 lines for a single transaction, please make sure to capture all lines for each transaction.
Put all credit card transactions in a table format with columns Date, Merchant, Amount, Card, Category and Account.
Since the statements may be hard to read, please make sure to capture all transactions, you may sum up the total spending and cross check with the statment total to ensure all transactions are captured.
Sometimes there is a row with 'DCC', the amount is 1% of the last transaction, this is a Dynamic Currency Conversion fee, add the amount to the last row.
Category should be one of the following: Cloud Services, Dining, Entertainment, Fuel, Health, Insurance, Others, Shopping, Telecom, Travel, Utilities.
Here is some example of transaction and their category.

### Cloud Services
DATAFORSEO

DIGITALOCEAN.COM

GOOGLE CLOUD

AMAZON WEB SERVICES

LANGCHAIN LANGSMITH

ATLASSIAN

GITHUB

### Dining

HANA-MUSUBI

CITY U AC1

### Entertainment

Patreon

### Fuel

### Health

PHYSICAL FITN

### Insurance

YF LIFE INSURANCE

BOWTIE LIFE INSURANCE

### Shopping

Decathlon

PAYME

### Telecom

HUTCHISON

HKBN-RESD

CLUB SIM

### Travel

HKEToll

OCTOPUS

### Utilities


For Account, please use one of the following: Personal, Business. Only Cloud Services can be categorized under Business, all other transactions should be under Personal.
"""
