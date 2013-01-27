from core.application import Application

if __name__ == "__main__":
    app = Application("server", {
        "device": {
        },
        "link": {
            "port": 20124,
        },
        "hooks": {
            "start": "/Users/ccp/code/simple-vpn/server.sh",
        }
        })
    app.run()
