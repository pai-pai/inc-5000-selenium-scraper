import csv
import logging
import time

from random import randint

import numpy as np
import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    MoveTargetOutOfBoundsException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


logging.basicConfig(level=logging.DEBUG, filename='logs.log')


SUMMARY_COLUMNS = ["Rank", "Company", "Description"]
DATA_COLUMNS = ["Industry", "Location", "Leadership", "Year Founded",
                "Company Size", "Website", "LinkedIn", "Twitter", "Facebook",
                "Key Clients", "Category Winner",]
COLUMNS = SUMMARY_COLUMNS + DATA_COLUMNS + ["Growth"]


def line_points(point1: tuple, point2: tuple):
    divider = 10000
    steps = randint(15, 25)
    x1, y1 = point1[0] / divider, point1[1] / divider
    x2, y2 = point2[0] / divider, point2[1] / divider
    x = np.linspace(x1, x2, steps)
    a = (y2 - y1) / (np.cosh(x2) - np.cosh(x1))
    b = y1 - a * np.cosh(x1)
    y = a * np.cosh(x) + b
    return list(x * divider), list(y * divider)


def to_xpath_string_literal(xpath_substring: str):
    if "'" not in xpath_substring:
        return f"'{xpath_substring}'"
    if '"' not in xpath_substring:
        return f'"{xpath_substring}"'
    return "concat('%s')" % xpath_substring.replace("'", "',\"'\",'")


class Runner:
    def __init__(self):
        self.data_file = "inc_5000_2022.csv"
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-default-browser-check")
        self.driver = uc.Chrome(options=options)

    def _curve_move(self, start_pos: tuple, element):
        element_rect = element.rect
        stop_pos = (
            randint(int(element_rect['x']), int(element_rect['x'] + element_rect['width'])),
            randint(int(element_rect['y']), int(element_rect['y'] + element_rect['height'])),
        )
        points = line_points(start_pos, stop_pos)
        points = zip(points[0], points[1])
        prev_x, prev_y = start_pos
        for point in points:
            ActionChains(self.driver)\
                .move_by_offset(point[0] - prev_x, point[1] - prev_y)\
                .perform()
            prev_x, prev_y = point[0], point[1]
        return stop_pos

    def _get_data(self, company_name, scroll_to=False):
        result = []
        try:
            company_container_el = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    f"//h2[contains(text(), {to_xpath_string_literal(company_name)})]/"
                    "ancestor::div[contains(@class, 'company-profile')]"
                ))
            )
        except TimeoutException:
            logging.warning("For some reason data container for %s is unreachable")
            return ['', company_name] + [''] * (len(COLUMNS) - 2)
        if scroll_to:
            logging.debug("Scroll to the bottom of container")
            try:
                ActionChains(self.driver)\
                    .scroll_to_element(company_container_el)\
                    .perform()
            except MoveTargetOutOfBoundsException:
                logging.warning(
                    "MoveTargetOutOfBoundsException occured during scrolling to %s",
                    company_name
                )
        company_container_el = self.driver.find_element(
            By.XPATH,
            f"//h2[contains(text(), {to_xpath_string_literal(company_name)})]/"
            "ancestor::div[contains(@class, 'company-profile')]"
        )
        company_container_html = company_container_el.get_attribute("outerHTML")
        soup = BeautifulSoup(company_container_html, "html.parser")
        summary = soup.find("div", class_="company-summary")
        data_points = soup.find("div", class_="company-datapoints")
        honors = soup.find("div", class_="company-honors")

        rank = summary.find("h2", class_="rank").text
        result.append(rank.replace("No.", "").replace(",", ""))
        result.append(summary.find("div", class_="headline-container").find("h2").string)
        result.append(summary.find("div", class_="summary-container").find("h3").string)
        for data in DATA_COLUMNS:
            value = data_points.find(string=data)
            result.append(
                value.find_parent("div", class_="row")
                .find("div", class_="details-container").string if value else ''
            )
        try:
            growth = honors.find("div", class_="standOut").find("em").string
        except AttributeError:
            growth = ''
        result.append(growth)
        return result

    def parse(self):
        self.driver.get("https://www.inc.com/inc5000/2022")

        try:
            # reset cursor position
            logo = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@class, 'logo-link')]"))
            )
            width, height = logo.rect['width'], logo.rect['height']
            x, y = logo.rect['x'], logo.rect['y']
            cursor_position = (width / 2 + x, height / 2 + y)
            logging.debug("Reset cursor to position %s", cursor_position)
            ActionChains(self.driver).move_to_element(logo).perform()

            logging.debug("Close cookies notification...")
            # close cookies notification
            cookies_notification = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    ".bcpNotificationBarClose.bcpNotificationBarCloseIcon"
                    ".bcpNotificationBarCloseTopRight"
                ))
            )
            cursor_position = self._curve_move(cursor_position, cookies_notification)
            ActionChains(self.driver)\
                .pause(1)\
                .click(cookies_notification)\
                .pause(randint(2,5))\
                .perform()

            logging.debug("Move to first company in list and go to the next page...")
            # move to first company in list and go to the next page
            first_company = WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "#rank-1 .company span"
                ))
            )
            company_name = first_company.get_attribute("textContent")
            company_href = self.driver.current_url
            cursor_position = self._curve_move(cursor_position, first_company)
            ActionChains(self.driver)\
                .pause(randint(1, 3))\
                .click(first_company)\
                .perform()

            # get data for every company
            WebDriverWait(self.driver, 60).until(EC.url_contains("profile"))
            with open(self.data_file, "a", encoding='utf-8') as data_file:
                data_writer = csv.writer(data_file)
                data_writer.writerow(COLUMNS)
                logging.debug("Getting data...")
                while True:
                    time.sleep(randint(2, 4))
                    logging.debug("Trying to get data for company %s...", company_name)
                    row = self._get_data(company_name, scroll_to=company_href is None)
                    data_writer.writerow(row)
                    logging.debug(row)
                    next_company_xpath = "//span[contains(text(), "\
                        f"{to_xpath_string_literal(company_name)})]/"\
                        "../../following-sibling::div[1]/a/span[contains(@class, 'name')]"
                    next_company_attempt = 0
                    while next_company_attempt <= 3:
                        try:
                            next_company = self.driver.find_element(By.XPATH, next_company_xpath)
                            company_name = next_company.get_attribute("textContent")
                            company_href = self.driver.find_element(
                                By.XPATH,
                                '//a[contains(@class, "fkoIAf")]/../following-sibling::div[1]/a'
                            ).get_attribute("href")
                            logging.debug("Trying to move to %s. Attempt #%s",
                                          company_name, next_company_attempt)
                            action = ActionChains(self.driver).move_to_element(next_company)
                            if company_href:
                                action.click()
                            action.perform()
                            time.sleep(randint(2, 4))
                            break
                        except (MoveTargetOutOfBoundsException, StaleElementReferenceException):
                            logging.warning("Somehow element is stale or out of clickable area."
                                            " Company %s", company_name)
                            time.sleep(randint(3, 5))
                        next_company_attempt += 1
                    else:
                        logging.error("It's not possible to move to the next company (%s)",
                                      company_name)
                        self.driver.close()
                        self.driver.quit()
        except (NoSuchElementException,
                StaleElementReferenceException,
                TimeoutException):
            logging.exception("An error occurred")
            self.driver.close()
            self.driver.quit()

        logging.debug("Finished")


if __name__ == "__main__":
    Runner().parse()
