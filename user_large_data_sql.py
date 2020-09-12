from flask import Flask, send_from_directory
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.exceptions import PreventUpdate
from dash_table.Format import Format, Scheme, Sign, Symbol

import dash_bootstrap_components as dbc
import dash_uploader as du

import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
from pathlib import Path
import uuid
from sqlalchemy import create_engine
import shutil
import time
import plotly.graph_objs as go
import base64
import io

APP_ID = 'user_large_data_sql'

layout = dbc.Container([
    html.H1('Large User Input File Upload'),
    dcc.Store(id=f'{APP_ID}_session_store'),
    dcc.Store(id=f'{APP_ID}_large_upload_fn_store'),
    dbc.Row([
        dbc.Col(
            du.Upload(id=f'{APP_ID}_large_upload')
        ),
        dbc.Col(
            dcc.Upload(
                id=f'{APP_ID}_dcc_upload',
                children=html.Div([
                    'dcc.Upload '
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=True
            ),
        )
    ]),
    dbc.ButtonGroup([
        dbc.Button('Process Data', id=f'{APP_ID}_process_data_button', color='primary', disabled=True)
    ]),
    dcc.Loading(
        children=dbc.Row([
            dbc.Col(
                dbc.FormGroup([
                    dbc.Label('X Axis'),
                    dbc.Select(id=f'{APP_ID}_xaxis_select')
                ])
            ),
            dbc.Col(
                dbc.FormGroup([
                    dbc.Label('Y Axis'),
                    dbc.Select(id=f'{APP_ID}_yaxis_select')
                ])
            )
        ]),
    ),
    dcc.Loading(
        html.Div(id=f'{APP_ID}_graph_div')
    ),
])


def add_dash(app):

    @du.callback(
        output=Output(f'{APP_ID}_large_upload_fn_store', 'data'),
        id=f'{APP_ID}_large_upload',
    )
    def get_a_list(filenames):
        return {i: filenames[i] for i in range(len(filenames))}


    @app.callback(
        Output(f'{APP_ID}_process_data_button', 'disabled'),
        [
            Input(f'{APP_ID}_large_upload_fn_store', 'data'),
            Input(f'{APP_ID}_dcc_upload', 'contents')
        ],
        [
            State(f'{APP_ID}_dcc_upload', 'filename')
        ]
    )
    def upload_data(dic_of_names, list_contents, list_names):
        # who done it?
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate

        if dic_of_names is None and list_contents is None:
            return True

        lines = []
        # dcc.upload component
        if ctx.triggered[0]['prop_id'].split('.')[0] == f'{APP_ID}_dcc_upload':
            for i, fn in enumerate(list_names):
                content_type, content_string = list_contents[i].split(',')
                decoded = base64.b64decode(content_string)
                line = ''
                while line.strip() == '':
                    line = io.StringIO(decoded.decode('utf-8')).readline()
                lines.append(line)
        # dash-uploader component
        elif ctx.triggered[0]['prop_id'].split('.')[0] == f'{APP_ID}_large_upload_fn_store':
            for k in dic_of_names.keys():
                fn = dic_of_names[k]
                with open(fn) as f:
                    while True:
                        line = next(f)
                        if line.strip() != '':
                            break
                lines.append(line)

        else:
            return True

        return False


    @app.callback(
        [
            Output(f'{APP_ID}_session_store', 'data'),
            Output(f'{APP_ID}_xaxis_select', 'options'),
            Output(f'{APP_ID}_yaxis_select', 'options'),
        ],
        [
            Input(f'{APP_ID}_process_data_button', 'n_clicks'),
        ],
        [
            State(f'{APP_ID}_large_upload_fn_store', 'data'),
            State(f'{APP_ID}_dcc_upload', 'contents'),
            State(f'{APP_ID}_dcc_upload', 'filename')
        ]
    )
    def process_data(n_clicks, dic_of_names, list_contents, list_names):
        if n_clicks is None:
            raise PreventUpdate

        # clean up old dbs
        p = Path.cwd() / Path("temp")
        [shutil.rmtree(pi) for pi in p.iterdir() if pi.is_dir() and time.time() - pi.stat().st_mtime > 10000]
        [pi.unlink() for pi in p.iterdir() if not pi.is_dir() and time.time() - pi.stat().st_mtime > 10000]

        if dic_of_names is None and list_contents is None:
            return [{}], None, None

        dfs = []
        if list_names is not None:
            for i, fn in enumerate(list_names):
                content_type, content_string = list_contents[i].split(',')
                decoded = base64.b64decode(content_string)
                # with open(decoded, 'rb') as f:
                lines = [l for l in io.StringIO(decoded.decode('utf-8')).readlines() if l.strip() != '']
                df = pd.read_json('[' + ','.join(lines) + ']', orient='records')
                df['fn'] = fn
                dfs.append(df)
        else:
            for k in dic_of_names.keys():
                fn = dic_of_names[k]
                with open(fn) as f:
                    lines = [l for l in f.readlines() if l.strip() != '']
                df = pd.read_json('[' + ','.join(lines) + ']', orient='records')
                df['fn'] = Path(fn).stem
                dfs.append(df)
        df = pd.concat(dfs, axis=0, ignore_index=True, sort=True)

        # create uniue filename and 'temp' folder if it doesnt exist
        sqdb_fn = f"{str(uuid.uuid4())}.db"
        ffname = Path.cwd() / Path("temp") / sqdb_fn
        Path.mkdir(ffname.parent, parents=True, exist_ok=True)

        # write data to local sqlite db file
        engine = create_engine('sqlite:///' + str(ffname))
        df.to_sql('my_data_table', con=engine)
        engine.dispose()

        cols = df.columns
        cols_axes = [{'label': c, 'value': c} for c in cols]

        return {'sqdb_fn': sqdb_fn}, cols_axes, cols_axes


    @app.callback(
        Output(f'{APP_ID}_graph_div', 'children'),
        [
            Input(f'{APP_ID}_xaxis_select', 'value'),
            Input(f'{APP_ID}_yaxis_select', 'value'),
        ],
        [
            State(f'{APP_ID}_session_store', 'data'),
        ]
    )
    def plot_data(xaxis, yaxis, store_data):
        if store_data is None:
            return [dbc.Alert('Upload & Process Data', color='primary')]
        if xaxis is None:
            return [dbc.Alert('Select x axis data', color='primary')]
        if yaxis is None:
            return [dbc.Alert('Select y axis data', color='primary')]


        sqdb_fn = store_data['sqdb_fn']
        ffname = Path.cwd() / Path("temp") / sqdb_fn
        Path.mkdir(ffname.parent, parents=True, exist_ok=True)

        engine = create_engine('sqlite:///' + str(ffname))

        df = pd.read_sql('SELECT * FROM my_data_table', con=engine)
        if xaxis not in df.columns:
            return [dbc.Alert('x axis not in columns', color='danger')]
        if yaxis not in df.columns:
            return [dbc.Alert('y axis not in columns', color='danger')]

        fig = go.Figure()
        fig.update_layout(showlegend=True)
        for name, dfi in df.groupby('fn'):
            fig.add_trace(
                go.Scattergl(
                    x=dfi[xaxis].tail(200000),
                    y=dfi[yaxis].tail(200000),
                    name=name
                )
            )

        return [dcc.Graph(figure=fig, config={'modeBarButtonsToAdd':['drawline', 'drawrect', 'drawopenpath', 'eraseshape']})]

    return app


if __name__ == '__main__':

    external_stylesheets = [
        dbc.themes.BOOTSTRAP,
    ]

    server = Flask(__name__)
    app = dash.Dash(__name__, server=server, external_stylesheets=external_stylesheets)
    app.config['suppress_callback_exceptions'] = True

    du.configure_upload(app, Path.cwd() / Path("temp"))

    app.layout = layout
    app = add_dash(app)
    app.run_server(debug=True)
