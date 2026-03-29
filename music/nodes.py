# music/nodes.py
# Local Lavalink running on the same VM as the bot.
# Falls back to public nodes if local fails.

LAVALINK_NODES = [
    # Local — fastest, most reliable, no YouTube blocking
    {
        "uri":      "http://localhost:2333",
        "password": "lumibot123",
        "name":     "local",
    },
    # Public fallbacks
    {
        "uri":      "http://lavalink.serenetia.com:80",
        "password": "https://dsc.gg/ajidevserver",
        "name":     "serenetia",
    },
    {
        "uri":      "http://lavalink.jirayu.net:13592",
        "password": "youshallnotpass",
        "name":     "jirayu",
    },
    {
        "uri":      "http://lavalink.devamop.in:80",
        "password": "DevamOP",
        "name":     "devamop",
    },
]