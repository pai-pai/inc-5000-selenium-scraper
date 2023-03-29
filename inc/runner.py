import csv
import logging
import time

from random import choice, randint

import numpy as np
import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


logging.basicConfig(level=logging.WARNING, filename='logs.log')


SUMMARY_COLUMNS = ["Rank", "Company", "Description"]
DATA_COLUMNS = ["Industry", "Location", "Leadership", "Year Founded",
                "Company Size", "Website", "LinkedIn", "Twitter", "Facebook",
                "Key Clients", "Category Winner",]
COLUMNS = SUMMARY_COLUMNS + DATA_COLUMNS + ["Growth"]


class Runner:
    def __init__(self):
        self.data_file = "inc_5000_2022.csv"
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-default-browser-check")
        self.driver = uc.Chrome(options=options)

    @staticmethod
    def _line_points(point1, point2):
        divider = 10000
        steps = randint(15, 25)
        x1, y1 = point1[0] / divider, point1[1] / divider
        x2, y2 = point2[0] / divider, point2[1] / divider
        x = np.linspace(x1, x2, steps)
        a = (y2 - y1) / (np.cosh(x2) - np.cosh(x1))
        b = y1 - a * np.cosh(x1)
        y = a * np.cosh(x) + b
        return list(x * divider), list(y * divider)

    def _curve_move(self, start_pos, element):
        element_rect = element.rect
        stop_pos = (
            randint(int(element_rect['x']), int(element_rect['x'] + element_rect['width'])),
            randint(int(element_rect['y']), int(element_rect['y'] + element_rect['height'])),
        )
        points = self._line_points(start_pos, stop_pos)
        points = zip(points[0], points[1])
        prev_x, prev_y = start_pos
        for point in points:
            ActionChains(self.driver)\
                .move_by_offset(point[0] - prev_x, point[1] - prev_y)\
                .perform()
            prev_x, prev_y = point[0], point[1]
        return stop_pos

    def _get_data(self, company_name):
        result = []
        company_container_el = WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((
                By.XPATH,
                f'//h2[contains(text(), "{company_name}")]/'
                'ancestor::div[contains(@class, "company-profile")]'
            ))
        )
        company_container_html = company_container_el.get_attribute("outerHTML")
        soup = BeautifulSoup(company_container_html, "html.parser")
        summary = soup.find("div", class_="company-summary")
        data_points = soup.find("div", class_="company-datapoints")
        honors = soup.find("div", class_="company-honors")

        rank = summary.find("h2", class_="rank").text
        result.append(rank.replace("No.", ""))
        result.append(summary.find("div", class_="headline-container").find("h2").string)
        result.append(summary.find("div", class_="summary-container").find("h3").string)
        for data in DATA_COLUMNS:
            value = data_points.find(string=data)
            result.append(
                value.find_parent("div", class_="row")
                .find("div", class_="details-container").string if value else ''
            )
        result.append(honors.find("div", class_="standOut").find("em").string)
        return result

    def parse(self):
        self.driver.get("https://www.inc.com/inc5000/2022")

        try:
            # reset cursor position
            html = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//html"))
            )
            width, height = html.rect['width'], html.rect['height']
            possible_offset = (
                (-width / 2, -randint(0, (height // 2))),
                (-randint(0, (width // 2)), -height // 2),
            )
            x_offset, y_offset = choice(possible_offset)
            cursor_position = (width / 2 + x_offset, height / 2 + y_offset)
            logging.warning(
                "Reset cursor to position %s. Offset x: %s, y: %s. Window size: %s x %s",
                cursor_position, x_offset, y_offset, width, height
            )
            ActionChains(self.driver)\
                .move_to_element_with_offset(html, x_offset, y_offset)\
                .perform()

            logging.warning("Close cookies notification...")
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
                .perform()

            logging.warning("Move to first company in list and go to the next page...")
            # move to first company in list and go to the next page
            first_company = WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "#rank-1 .company span"
                ))
            )
            company_name = first_company.get_attribute("textContent")
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
                logging.warning("Getting data...")
                while True:
                    time.sleep(randint(2, 4))
                    row = self._get_data(company_name)
                    data_writer.writerow(row)
                    logging.warning("VVV Collected row VVV")
                    logging.warning(row)
                    next_company_xpath = '//a[contains(@class, "fkoIAf")]/..'\
                        '/following-sibling::div[1]/a/span[contains(@class, "name")]'
                    next_company_attempt = 0
                    while next_company_attempt <= 3:
                        try:
                            next_company = self.driver.find_element(By.XPATH, next_company_xpath)
                            company_name = next_company.get_attribute("textContent")
                            company_href = self.driver.find_element(
                                By.XPATH,
                                '//a[contains(@class, "fkoIAf")]/../following-sibling::div[1]/a'
                            ).get_attribute("href")
                            logging.warning("Company name: %s, href: %s",
                                            company_name, company_href)
                            logging.warning("Trying to move to %s. Attempt #%s",
                                            company_name, next_company_attempt)
                            ActionChains(self.driver).move_to_element(next_company)\
                                .click().perform()
                            break
                        except StaleElementReferenceException:
                            logging.error("Somehow it's stale. Company %s", company_name)
                            time.sleep(randint(3, 5))
                        next_company_attempt += 1
                    else:
                        logging.error("It's not possible to move to next company (%s)",
                                      company_name)
                        self.driver.close()
                        self.driver.quit()
        except (NoSuchElementException, TimeoutException):
            logging.exception("VVV An error occurred VVV")
            self.driver.close()
            self.driver.quit()

        logging.warning("Finished")


if __name__ == "__main__":
    Runner().parse()
