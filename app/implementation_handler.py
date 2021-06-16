# ******************************************************************************
#  Copyright (c) 2020 University of Stuttgart
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ******************************************************************************
import urllib
from urllib import request, error
import tempfile
import os, sys, shutil
from importlib import reload

from flask_restful import abort
from pyquil import Program
from urllib3 import HTTPResponse

from app import app


def prepare_code_from_data(data, input_params):
    """Get implementation code from data. Set input parameters into implementation. Return circuit."""
    temp_dir = tempfile.mkdtemp()
    with open(os.path.join(temp_dir, "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(temp_dir, "downloaded_code.py"), "w") as f:
        f.write(data)
    sys.path.append(temp_dir)
    try:
        import downloaded_code

        # deletes every attribute from downloaded_code, except __name__, because importlib.reload
        # doesn't reset the module's global variables
        for attr in dir(downloaded_code):
            if attr != "__name__":
                delattr(downloaded_code, attr)

        reload(downloaded_code)
        if 'get_circuit' in dir(downloaded_code):
            circuit = downloaded_code.get_circuit(**input_params)
        elif 'qc' in dir(downloaded_code):
            circuit = downloaded_code.qc
        elif 'p' in dir(downloaded_code):
            circuit = downloaded_code.p
    finally:
        sys.path.remove(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    if not circuit:
        raise ValueError
    return circuit


def prepare_code_from_url(url, input_params, bearer_token: str = ""):
    """Get implementation code from URL. Set input parameters into implementation. Return circuit."""
    try:
        impl = _download_code(url, bearer_token)
    except (error.HTTPError, error.URLError):
        return None

    circuit = prepare_code_from_data(impl, input_params)
    return circuit


def prepare_code_from_quil(quil):
    return Program(quil)


def prepare_code_from_quil_url(url, bearer_token: str = ""):
    """Get implementation code from URL. Set input parameters into implementation. Return circuit."""
    try:
        impl = _download_code(url, bearer_token)
    except (error.HTTPError, error.URLError):
        return None

    return prepare_code_from_quil(impl)


def _download_code(url: str, bearer_token: str = "") -> str:
    req = request.Request(url)

    if urllib.parse.urlparse(url).netloc == "platform.planqk.de":
        if bearer_token == "":
            app.logger.error("No bearer token specified, download from the PlanQK platform will fail.")

            abort(401)
        elif bearer_token.startswith("Bearer"):
            app.logger.error("The bearer token MUST NOT start with \"Bearer\".")

            abort(401)

        req.add_header("Authorization", "Bearer " + bearer_token)

    try:
        res: HTTPResponse = request.urlopen(req)
    except Exception as e:
        app.logger.error("Could not open url: " + str(e))

        if str(e).find("401") != -1:
            abort(401)

    if res.getcode() == 200 and urllib.parse.urlparse(url).netloc == "platform.planqk.de":
        app.logger.info("Request to platform.planqk.de was executed successfully.")

    if res.getcode() == 401:
        abort(401)

    return res.read().decode("utf-8")
