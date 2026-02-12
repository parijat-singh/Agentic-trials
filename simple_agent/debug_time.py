from tools import get_time
import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

print(f"Current System Time (datetime.now()): {datetime.datetime.now()}")
print(f"Current UTC Time: {datetime.datetime.now(datetime.timezone.utc)}")
print(f"Tool Output (PST): {get_time('America/Los_Angeles')}")
print(f"Tool Output (UTC): {get_time('UTC')}")
