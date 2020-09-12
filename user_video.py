from flask import Flask, send_from_directory
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate

import dash_bootstrap_components as dbc
import dash_uploader as du
from dash_extensions.enrich import Dash, ServersideOutput, Output, Input, State, Trigger

import numpy as np
from pathlib import Path
import uuid
import io
from base64 import b64encode
from PIL import Image

import moviepy.editor as mpy

APP_ID = 'user_large_video'

layout = dbc.Container([
    html.H1('My Video Editor'),
    dcc.Store(id=f'{APP_ID}_large_upload_fn_store'),
    du.Upload(id=f'{APP_ID}_large_upload', max_file_size=5120),
    dbc.Row([
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Subclip Start (s)'),
                dbc.Input(id=f'{APP_ID}_t_start_input', type='number')
            ]),
            dbc.FormGroup([
                dbc.Label('Crop Bottom (px)'),
                dbc.Input(id=f'{APP_ID}_crop_bot_input', type='number', value=0)
            ])
        ]),
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Subclip End(s)'),
                dbc.Input(id=f'{APP_ID}_t_end_input', type='number')
            ]),
            dbc.FormGroup([
                dbc.Label('Crop Top (px)'),
                dbc.Input(id=f'{APP_ID}_crop_top_input', type='number', value=0)
            ])
        ]),
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Video Width (px)'),
                dbc.Input(id=f'{APP_ID}_vid_w_input', type='number')
            ])
        ])

    ]),
    dbc.Row([
        dbc.Col(
            dbc.FormGroup([
                dbc.Label('Text Overlay'),
                dbc.Input(id=f'{APP_ID}_text_input', debounce=True)
            ])
        ),
        dbc.Col(
            dbc.FormGroup([
                dbc.Label('Font'),
                dbc.Select(id=f'{APP_ID}_font_select',
                           options=[{"label": f, "value": f} for f in mpy.TextClip.list('font')],
                           value=mpy.TextClip.list('font')[0]
                           )
            ])
        )
    ]),
    dbc.ButtonGroup([
        dbc.Button('Process Video', id=f'{APP_ID}_process_video_button', color='primary', disabled=True),
        html.A(
            dbc.Button('Download Video', id=f'{APP_ID}_download_button', color='primary', disabled=True),
            id=f'{APP_ID}_download_link',
            href=''
        )
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Loading(
                html.Div(id=f'{APP_ID}_image_div')
            ),
        ]),
        dbc.Col(
            dcc.Loading(
                html.Div(id=f'{APP_ID}_video_div')
            ),
        )
    ]),
])


def add_dash(app):

    @du.callback(
        output=Output(f'{APP_ID}_large_upload_fn_store', 'data'),
        id=f'{APP_ID}_large_upload',
    )
    def get_a_list(filenames):
        return {i: filenames[i] for i in range(len(filenames))}


    @app.callback(
        [
            Output(f'{APP_ID}_process_video_button', 'disabled'),
            Output(f'{APP_ID}_t_start_input', 'value'),
            Output(f'{APP_ID}_t_end_input', 'value'),
            Output(f'{APP_ID}_vid_w_input', 'value')
        ],
        [
            Input(f'{APP_ID}_large_upload_fn_store', 'data'),
        ],
    )
    def upload_video(dic_of_names):
        if dic_of_names is None:
            return True, 0., None, None

        clip_1 = mpy.VideoFileClip(dic_of_names[list(dic_of_names)[0]])

        return False, 0., clip_1.duration, clip_1.size[0]


    @app.callback(
        Output(f'{APP_ID}_image_div', 'children'),
        [
            Input(f'{APP_ID}_font_select', 'value'),
            Input(f'{APP_ID}_vid_w_input', 'value'),
            Input(f'{APP_ID}_large_upload_fn_store', 'data'),
            Input(f'{APP_ID}_text_input', 'value'),
            Input(f'{APP_ID}_t_start_input', 'value'),
            Input(f'{APP_ID}_t_end_input', 'value'),
            Input(f'{APP_ID}_crop_bot_input', 'value'),
            Input(f'{APP_ID}_crop_top_input', 'value'),
        ],
    )
    def frame_out(font, video_width, dic_of_names, text, clip_1_start, clip_1_end, crop_bot, crop_top):
        if any([v is None for v in [font, video_width, dic_of_names, text, crop_bot, crop_top]]):
            raise PreventUpdate

        clip_1 = mpy.VideoFileClip(dic_of_names[list(dic_of_names)[0]])
        clip_1 = clip_1.fx(mpy.vfx.resize, width=video_width)
        clip_1 = clip_1.subclip(t_start=clip_1_start, t_end=clip_1_end)
        clip_1 = clip_1.fx(mpy.vfx.crop, y1=crop_top, y2=clip_1.size[1]-crop_bot)
        txt_clip = mpy.TextClip(text,
                           size=clip_1.size,
                           color='white',
                           bg_color='black',
                           font=font
                           ).set_duration(clip_1.duration)
        # for image export in memory using PIL (for base64 convert), need to apply mask manually
        f = clip_1.fx(mpy.vfx.resize, width=540).get_frame(t=0)
        mask = 255 * txt_clip.fx(mpy.vfx.resize, width=540).to_mask().get_frame(t=0)
        ff = np.dstack([f, mask]).astype('uint8')

        im = Image.fromarray(ff)
        rawBytes = io.BytesIO()
        im.save(rawBytes, "PNG")
        rawBytes.seek(0)

        return html.Img(src=f"data:image/PNG;base64, {b64encode(rawBytes.read()).decode('utf-8')}")



    @app.callback(
        [
            Output(f'{APP_ID}_video_div', 'children'),
            Output(f'{APP_ID}_download_link', 'href'),
            Output(f'{APP_ID}_download_button', 'disabled'),
         ],
        [
            Input(f'{APP_ID}_process_video_button', 'n_clicks'),
        ],
        [
            State(f'{APP_ID}_large_upload_fn_store', 'data'),
            State(f'{APP_ID}_t_start_input', 'value'),
            State(f'{APP_ID}_t_end_input', 'value'),
            State(f'{APP_ID}_vid_w_input', 'value'),
            State(f'{APP_ID}_text_input', 'value'),
            State(f'{APP_ID}_font_select', 'value'),
            State(f'{APP_ID}_crop_bot_input', 'value'),
            State(f'{APP_ID}_crop_top_input', 'value'),
        ]
    )
    def process_pre_video(n_clicks, dic_of_names, clip_1_start, clip_1_end, video_width, text, font, crop_bot, crop_top):
        if n_clicks is None:
            raise PreventUpdate

        if dic_of_names is None:
            return None

        if text is None:
            text = ''
        clip_1 = mpy.VideoFileClip(dic_of_names[list(dic_of_names)[0]])
        clip_1 = clip_1.fx(mpy.vfx.resize, width=video_width)
        clip_1 = clip_1.subclip(t_start=clip_1_start, t_end=clip_1_end)
        clip_1 = clip_1.fx(mpy.vfx.crop, y1=crop_top, y2=clip_1.size[1]-crop_bot)
        txt_clip = mpy.TextClip(text,
                           size=clip_1.size,
                           color='white',
                           bg_color='black',
                           font=font
                           ).set_duration(clip_1.duration)
        clip_1 = clip_1.set_mask(txt_clip.to_mask())

        ffname = Path("downloads") / f'{str(uuid.uuid4())}.mp4'
        Path.mkdir(ffname.parent, parents=True, exist_ok=True)
        cvc = mpy.CompositeVideoClip([clip_1], bg_color=(255, 255, 255))
        # preview video set to 540 width and 5 fps
        fn_pre = '.'.join(str(ffname).split('.')[:-1]) + 'preview_.webm'
        cvc.fx(mpy.vfx.resize, width=540).write_videofile(fn_pre, audio=False, fps=5)
        # write full deal
        cvc.write_videofile(str(ffname), audio=False, fps=clip_1.fps)

        vid = open(fn_pre, 'rb')
        base64_data = b64encode(vid.read())
        base64_string = base64_data.decode('utf-8')
        return [html.Video(src=f'data:video/webm;base64,{base64_string}', controls=True)], f'/{ffname}', False


    return app


if __name__ == '__main__':

    external_stylesheets = [
        dbc.themes.BOOTSTRAP,
    ]

    server = Flask(__name__)
    app = Dash(__name__, server=server, external_stylesheets=external_stylesheets)
    app.config['suppress_callback_exceptions'] = True

    @app.server.route('/downloads/<path:path>')
    def serve_static(path):
        return send_from_directory(
            Path("downloads"), path, as_attachment=True
        )

    du.configure_upload(app, Path.cwd() / Path("temp"))

    app.layout = layout
    app = add_dash(app)
    app.run_server(debug=True)