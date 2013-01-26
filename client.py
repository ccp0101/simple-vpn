from core.application import Application

if __name__ == "__main__":
    app = Application("client", {
        "device": {
            "port": 20123,
        },
        "link": {
            "port": 80,
            "host": "127.0.0.1",
        },
        "hooks": {
            "start": "/Users/ccp/code/simple-vpn/start.sh",
            "stop": "/Users/ccp/code/simple-vpn/stop.sh"
        }
        })
    app.run()
