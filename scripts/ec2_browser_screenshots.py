"""Headless-Chrome screenshots of the app running on the EC2 public IP."""
import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(__file__))
from render_terminal_png import add_url_bar  # noqa: E402

ip = sys.argv[1]
OUT = "evidence/screenshots"
shots = [
    (f"http://{ip}/", "53_browser_app_on_ec2_public_ip", 1280, 760),
    (f"http://{ip}/api/info", "54_browser_ec2_api_info", 1000, 420),
    (f"http://{ip}/api/tasks", "55_browser_ec2_api_tasks", 1000, 420),
]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for url, name, w, h in shots:
        ctx = b.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_timeout(800)
        path = f"{OUT}/{name}.png"
        page.screenshot(path=path)
        add_url_bar(path, f"{url}   (AWS EC2 t3.micro, ap-south-1, created by Terraform from Jenkins build #5)")
        print(path)
        ctx.close()
    b.close()
