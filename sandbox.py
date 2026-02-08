#%%
from pymessage import get_messages, find_backups



# %%
from pymessage import get_messages, find_backups

# Find backups
backups = find_backups()
print(f"Found {len(backups)} backups")

# Get all messages
df = get_messages(
    backup_path=backups[0]["path"],
    phone_numbers='9714205397')

df.head()

# # Filter by phone and date
# df = get_messages(
#     backup_path="/path/to/backup",
#     phone_numbers="+1234567890",
#     date_range=("2024-01-01", "2024-12-31"),
#     output_csv="messages.csv"
# )

# %%
# Find backups
backups = find_backups()
print(f"Found {len(backups)} backups")
# %%
