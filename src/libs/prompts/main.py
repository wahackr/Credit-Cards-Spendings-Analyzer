STATEMENT_TEXT_INSTRUCTIONS = """
Analyze the credit card statement text below, list out all the transactions with date (YYYY-MM-DD), transaction name and amount. Payment credits can be ignored.
The text is extracted from the statement PDF as Markdown, so transaction rows usually appear as table rows such as:
| Date | Description | Amount (USD) | Amount (HKD) |
Always return a Statement structured response. If the statement contains no transaction rows, return an empty transactions list, with number_of_transactions set to 0 and total_spending set to 0. Do not invent transactions or statement metadata.
Some statements include the original currency and amount, but please always use the HKD column for analysis.
A transaction may span several lines or table rows, please make sure to capture all lines for each transaction. When a row has an empty date, it continues the previous transaction: merge it into that transaction instead of returning it as a separate transaction.
Dates may omit the year, please take the year from the statement period or from the neighbouring rows.
Some transactions are pretty much the same and continuously repeated, please make sure to capture all transactions, even if they looks repeated.
Sum up the transaction amounts and cross check with the statement total spending to ensure all transactions are captured.
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
