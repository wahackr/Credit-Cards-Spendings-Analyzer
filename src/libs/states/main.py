from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Individual transaction with name and amount."""

    date: str = Field(description="Date of the transaction, in YYYY-MM-DD format")
    transaction_name: str = Field(description="Name of the transaction")
    amount: float = Field(description="Transaction amount")
    category: str = Field(description="Category of the transaction")
    account: str = Field(description="Account associated with the transaction, either Personal or Business")
    card_name: str = Field(description="Name of the credit card used for the transaction")


class Statement(BaseModel):
    """Structured output returned by the statement reader agent."""

    transactions: list[Transaction] = Field(
        description="List of transactions with name and amount",
        default_factory=list
    )

    card_name: str = Field(
        description="Name of the credit card",
    )

    total_spending: float = Field(
        description="Total spending amount",
    )

    number_of_transactions: int = Field(
        description="Total number of transactions",
    )

    due_date: str = Field(
        description="Due date of the statement",
    )
