from map_builder import (
    build_layers,
    build_app,
    DailyMarkerIndex,
    PrecinctLayer,
    ShelterLayer,
    PRECINCT_PATH,
    NIBRS_PATH,
    SHELTER_PATH,
)

layers = build_layers()
index = DailyMarkerIndex(layers)
precinct_layer = PrecinctLayer()
precinct_layer.load(PRECINCT_PATH, NIBRS_PATH)
shelter_layer = ShelterLayer()
shelter_layer.load(SHELTER_PATH)

app = build_app(index, layers, precinct_layer, shelter_layer)
server = app.server  # gunicorn entry point: app:server

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
