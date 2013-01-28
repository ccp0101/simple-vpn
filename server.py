from core.application import Application

if __name__ == "__main__":
    app = Application("server", {
        "device": {
        },
        "link": {
            "port": 20124,
        },
        "network": "10.48.0.0/24"
        })
    app.run()
