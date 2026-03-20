#!/usr/bin/env python3
from cloud_jinja2 import Environment
from cloud_jinja2.loaders import FileSystemLoader

env = Environment(loader=FileSystemLoader("templates"))

tmpl = env.get_template("broken.html")
print(tmpl.render(seq=[3, 2, 4, 5, 3, 2, 0, 2, 1]))
