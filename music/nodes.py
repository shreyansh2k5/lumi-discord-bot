# music/nodes.py
# Curated public Lavalink v4 nodes — these handle YouTube server-side.
# No cookies or tokens needed on our end.
# Tried in order until one connects successfully.

LAVALINK_NODES = [
    # serenetia — monitored 24/7, YouTube explicitly supported
    {
        "uri":      "http://lavalink.serenetia.com:80",
        "password": "https://dsc.gg/ajidevserver",
        "secure":   False,
    },
    {
        "uri":      "https://lavalink.serenetia.com:443",
        "password": "https://dsc.gg/ajidevserver",
        "secure":   True,
    },
    # darrennathanael — weekly quality checked
    {
        "uri":      "http://lavalink.darrennathanael.com:2333",
        "password": "SkibidiToilet",
        "secure":   False,
    },
    # jirayu
    {
        "uri":      "http://lavalink.jirayu.net:13592",
        "password": "youshallnotpass",
        "secure":   False,
    },
    # devamop
    {
        "uri":      "http://lavalink.devamop.in:80",
        "password": "DevamOP",
        "secure":   False,
    },
]