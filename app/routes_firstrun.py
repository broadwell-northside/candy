# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""First-run routes: the PHASE_TWO switch, and SD 1.5 in the tool list."""
import phase_two


def register(server):
    app = server.app

    @app.get("/api/phase_two")
    def phase_two_get():
        return {"hidden": phase_two.hidden(server.OUT)}

    @app.post("/api/phase_two")
    def phase_two_set(body: dict = server.Body(...)):
        if not isinstance(body.get("hidden"), bool):
            server.err("Say true or false for hidden.")
        return {"hidden": phase_two.set_hidden(server.OUT, body["hidden"])}

    server.FEATURES.append(("create_sd15", "Create: Photo (SD 1.5)", ["image_sd15_api.json"]))
