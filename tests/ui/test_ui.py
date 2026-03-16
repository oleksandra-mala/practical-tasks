from playwright.sync_api import sync_playwright


def test_run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://the-internet.herokuapp.com/login")
        print(page.title())
        browser.close()