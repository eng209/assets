import numpy as np
import pandas as pd
import plotly.graph_objects as go  # type: ignore

from numpy.typing import NDArray
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator


def viz3D(model: Pipeline, *data: pd.DataFrame) -> None:
    salinity: NDArray[np.float64] = np.linspace(0, 40, 100)
    temperature: NDArray[np.float64] = np.linspace(18, 34, 100)
    depth: NDArray[np.float64] = np.asarray(pd.concat([df.depth for df in data])).mean()

    surf_X = np.transpose(
        [
            np.tile(salinity, len(temperature)),
            np.repeat(temperature, len(salinity)),
            np.full(len(temperature) * len(salinity), depth),
        ]
    )

    surf_y = np.asarray(model.predict(surf_X))

    fig = go.Figure(
        data=[
            go.Scatter3d(
                z=df.velocity,
                x=df.salinity.values,
                y=df.temperature.values,
                mode="markers",
                marker_size=4,
            )
            for df in data
        ]
        + [
            go.Surface(
                z=surf_y.reshape(100, 100),
                x=salinity,
                y=temperature,
                cmin=1400,
                cmax=1600,
            )
        ]
    )

    fig.update_layout(
        title="Velocity",
        autosize=False,
        width=800,
        height=800,
        margin=dict(l=50, r=50, b=50, t=50),
        scene=dict(
            xaxis=dict(title="x:Salinity"),
            yaxis=dict(title="y:Temperature"),
            zaxis=dict(title="z:Velocity"),
        ),
        legend=dict(xanchor="left", yanchor="top", x=0.01, y=0.99),
        scene_camera=dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=-1.25, y=-1.25, z=0.25),
        ),
    )

    fig.show()
