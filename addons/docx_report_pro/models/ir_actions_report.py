# Copyright 2019-2021 Artem Shurshilov
# Odoo Proprietary License v1.0

# This software and associated files (the "Software") may only be used (executed,
# modified, executed after modifications) if you have purchased a valid license
# from the authors, typically via Odoo Apps, or if you have received a written
# agreement from the authors of the Software (see the COPYRIGHT file).

# You may develop Odoo modules that use the Software as a library (typically
# by depending on it, importing it and using its resources), but without copying
# any source code or material from the Software. You may distribute those
# modules under the license of your choice, provided that this license is
# compatible with the terms of the Odoo Proprietary License (For example:
# LGPL, MIT, or proprietary licenses similar to this one).

# It is forbidden to publish, distribute, sublicense, or sell copies of the Software
# or modified copies of the Software.

# The above copyright notice and this permission notice must be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import base64
import io
import logging
import os
import subprocess
import sys

from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
import datetime


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _get_path_source(self):
        if sys.platform == "win32":
            return r"C:\temp\backups\out.docx"
        return "/tmp/backups/out.docx"

    def _get_path_convert(self):
        if sys.platform == "win32":
            return r"C:\temp\backups"
        return "/tmp/backups"

    def _get_path_libreoffice(self):
        # TODO: Provide support for more platforms
        if sys.platform == "darwin":
            return "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if sys.platform == "win32":
            return r"C:\Program Files\LibreOffice\program\soffice.exe"
        return "libreoffice"

    report_type = fields.Selection(
        selection_add=[("docx", "DOCX")],
        ondelete={"docx": "cascade"},
        help="Extension of report fish",
    )
    out_report_type = fields.Selection(
        selection=[
            ("docx", "DOCX"),
            ("pdf", "PDF"),
            ("odt", "ODT"),
            ("html", "HTML"),
        ],
        help="Extension will download users. ATTENTION:doc!=docx",
        default="docx",
    )
    python_function_prepare = fields.Boolean(
        string="Enable python method of model for prepare data", default=False
    )
    python_function_name = fields.Char(
        string="Python method of model for prepare data",
        help="Return dict with values for insert into template",
    )
    template_docx = fields.Binary(
        string="Docx template",
        attachment=True,
        help="File with fish in report type format",
    )
    path_source = fields.Char(
        string="OS path to source file temporary", default=_get_path_source
    )
    path_convert_folder = fields.Char(
        string="OS path to converted file temporary", default=_get_path_convert
    )
    path_libreoffice = fields.Char(
        string="OS path to libreoffice",
        default=_get_path_libreoffice,
        help="For linux just libreoffice",
    )

    def _stringToRGB(self, base64_string):
        imgdata = base64.b64decode(str(base64_string))
        return io.BytesIO(imgdata).read()

    @staticmethod
    def update_images(context, templ, templ_copy):
        """
        try insert images one by one, if get error then just pass image
        work in copy tmpl for avoid errors
        """
        # image to insert as loop or field
        # if find __insert then understood that it will be loop with image
        for item, value in context.items():
            if "__insert" in item:
                new_images = []
                for image_dict in value:
                    params = {}
                    if "h" in image_dict:
                        params["height"] = Mm(image_dict["h"])
                    if "w" in image_dict:
                        params["width"] = Mm(image_dict["w"])
                    if "img" in image_dict:
                        stream = io.BytesIO(base64.b64decode(image_dict["img"]))
                        image_dict["img"] = InlineImage(templ, stream, **params)

                    else:
                        image_dict["img"] = InlineImage(
                            templ, io.BytesIO(""), **params
                        )
                    new_images.append(image_dict)
                context[item] = new_images
        # images to replace
        if "images" in context:
            i = 1
            for image in context["images"]:
                if not image:
                    imgdata = base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
                    )
                else:
                    imgdata = base64.b64decode(image)
                templ_copy.pic_to_replace[str(i) + ".jpg"] = io.BytesIO(
                    imgdata
                ).getvalue()
                myioc = io.BytesIO()
                try:
                    templ_copy.render(context)
                    templ_copy.save(myioc)
                except Exception as e:
                    # if get error render image delete this image and rerender
                    del templ_copy.pic_to_replace[str(i) + ".jpg"]
                    _logger.error(
                        "Error render tpl with image: "
                        + str(i)
                        + ".jpg "
                        + str(e)
                    )
                    raise UserError(
                        "Error render tpl with image: "
                        + str(i)
                        + ".jpg "
                        + str(e)
                    )
                i += 1
            # dict image which insert without errors
            templ.pic_to_replace = templ_copy.pic_to_replace
            templ.render(context)
            myio = io.BytesIO()
            templ.save(myio)
            return myio
        else:
            myio = io.BytesIO()
            templ.render(context)
            templ.save(myio)
            return myio

    def _render_docx(self, report_ref, res_ids, data=None):
        return self.render_docx(report_ref, res_ids, data)

    @api.model
    def render_docx(self, report_ref, docids, data=None):
        self = self.sudo()
        if not data:
            data = {}
        data.setdefault("report_type", "docx")
        report = self._get_report(report_ref)
        data = self._get_rendering_context(report, docids, data)
        # READ DATA
        content = base64.b64decode(self.template_docx)
        templ = DocxTemplate(io.BytesIO(content))
        templ_copy = DocxTemplate(io.BytesIO(content))

        path_source = self.path_source
        # add timestamp for files concurrent write
        if len(self.path_source.split(".")) == 2:
            path_source = (
                self.path_source.split(".")[0]
                + datetime.datetime.now().strftime("%y%m%d%H%M%S.")
                + self.path_source.split(".")[1]
            )

        for doc in data["docs"]:
            # add all record fields by default data to insert
            context = doc.sudo().read()[0]

            # add prepare python method data to insert
            if self.python_function_prepare:
                method = getattr(doc, self.python_function_name, False)
                if not method:
                    raise UserError(
                        _(
                            "Method %s not implemented in %s"
                            % (self.python_function_name, doc)
                        )
                    )
                context.update(method() or {})
            # fields = doc._fields
            # for i in fields:
            #     if i.type == 'binary':

            # replace all images inside docx 1.jpg,2.jpg to to images form context
            # context.update({"images": [doc.partner_id.image_1920]})
            # if "images" in context:
            #     i = 1
            #     for image in context["images"]:
            #         if not image:
            #             imgdata = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
            #         else:
            #             imgdata = base64.b64decode(image)
            #         templ.pic_to_replace[str(i)+".jpg"] = io.BytesIO(imgdata).getvalue()
            #         i += 1
            # templ.render(context)
        # other_file_obj = io.BytesIO(other_input_stream)
        # doc.replace_media('image.png', other_file_obj)

        # WRITE DATA
        # myio = io.BytesIO()
        myio = self.update_images(context, templ, templ_copy)
        # templ.save(myio)

        if self.out_report_type != "docx":
            if not os.path.isdir(self.path_convert_folder):
                os.makedirs(self.path_convert_folder)

            # WRITE DOCX SOURCE
            with open(path_source, "wb") as f:
                f.write(myio.getbuffer())

            # CONVERT DOCX TO out_report_type
            def convert_to(folder, source, timeout=None):
                args = [
                    self.path_libreoffice,
                    "--headless",
                    "--convert-to",
                    self.out_report_type,
                    "--outdir",
                    folder,
                    source,
                ]
                process = subprocess.run(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                )

            convert_to(self.path_convert_folder, path_source)

            # READ out_report_type file FROM OS
            myio = io.BytesIO()
            with open(
                path_source.replace("docx", self.out_report_type), "rb"
            ) as fin:
                myio = io.BytesIO(fin.read())

            try:
                os.unlink(path_source)
                os.unlink(path_source.replace("docx", self.out_report_type))
            except OSError:
                _logger.error(
                    "Error when trying to remove file %s" % path_source
                )

            return myio.getvalue(), self.out_report_type
        else:
            return myio.getvalue(), "docx"
