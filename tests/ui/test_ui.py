from playwright.sync_api import sync_playwright
from pages.login_page import LoginPage

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        login_page = LoginPage(page)
        login_page.open()
        login_page.login("tomsmith", "SuperSecretPassword!")

        browser.close()

run()


