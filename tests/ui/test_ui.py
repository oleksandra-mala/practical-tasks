from playwright.sync_api import sync_playwright, Page
from tests.pages.login_page import LoginPage

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page: Page = browser.new_page()

        login_page = LoginPage(page)
        login_page.open()
        login_page.login("tomsmith", "SuperSecretPassword!")

        if login_page.is_logged_in():
            print("Login successful")
        else:
            print("Login failed")

        browser.close()

run()


