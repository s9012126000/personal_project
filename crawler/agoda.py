from personal_project.config.mongo_config import *
from personal_project.config.crawler_config import *
import threading
import queue
import time
import json


class Worker(threading.Thread):
    def __init__(self, worker_num, driver):
        threading.Thread.__init__(self)
        self.worker_num = worker_num
        self.driver = driver

    def run(self):
        while not job_queue.empty():
            self.get_region_hotels(job_queue.get())

    def get_region_hotels(self, div):
        url = 'https://www.agoda.com/zh-tw/'
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until(
            ec.element_to_be_clickable((By.XPATH, "//input[@data-selenium='textInput']"))
        ).click()
        self.driver.find_element(By.XPATH, "//input[@data-selenium='textInput']").send_keys(div)
        WebDriverWait(self.driver, 10).until(
            ec.element_to_be_clickable((By.XPATH, "//li[@data-selenium='autosuggest-item']"))
        ).click()
        time.sleep(1)
        self.driver.find_element(By.XPATH, "//li[@data-selenium='allRoomsTab']").click()
        self.driver.find_element(By.XPATH, "//button[@data-selenium='searchButton']").click()
        try:
            WebDriverWait(self.driver, 10).until(
                ec.element_to_be_clickable((By.XPATH, "//button[@data-element-name='asq-ssr-popup-no-button']"))
            ).click()
        except TimeoutException:
            pass
        self.get_hotels()

    def get_hotels(self):
        col = client['personal_project']['agodacom']
        while True:
            self.scroll_to_bottom()
            try:
                cards = WebDriverWait(self.driver, 10).until(
                    ec.presence_of_all_elements_located((By.XPATH, "//a[@class='PropertyCard__Link']"))
                )
            except TimeoutException:
                print('end of this pages')
                break
            cards = [x.get_attribute('href') for x in cards if x.get_attribute('href') is not None]
            print(f'hotel cards per page: {len(cards)}')
            hotel_ls = []
            for c in cards:
                self.driver.execute_script("window.open()")
                WebDriverWait(self.driver, 10).until(ec.number_of_windows_to_be(2))
                self.driver.switch_to.window(self.driver.window_handles[1])
                self.driver.get(c)
                time.sleep(1)

                def fetching():
                    wait = WebDriverWait(self.driver, 5)
                    name = wait.until(
                        ec.presence_of_element_located((By.XPATH, "//h1[@data-selenium='hotel-header-name']"))
                    ).text
                    address = wait.until(
                        ec.presence_of_element_located((By.XPATH, "//span[@data-selenium='hotel-address-map']"))
                    ).text
                    link = self.driver.current_url
                    try:
                        rating = wait.until(
                            ec.presence_of_element_located((By.XPATH, "//div[@class='ReviewScoreCompact__section']"))
                        ).text
                    except TimeoutException:
                        rating = "No enough record"
                    try:
                        img = wait.until(
                            ec.presence_of_element_located((By.ID, 'PropertyMosaic'))
                        ).find_element(By.TAG_NAME, 'img').get_attribute('src')
                    except TimeoutException:
                        img = "non-provided"
                    try:
                        des = wait.until(
                            ec.presence_of_element_located((By.XPATH, "//div[@data-element-name='property-short-description']"))
                        ).text
                    except TimeoutException:
                        des = "non-provided"
                    try:
                        star = wait.until(
                            ec.presence_of_element_located((By.XPATH, "//i[@data-selenium='mosaic-hotel-rating']"))
                        ).get_attribute('class')
                    except TimeoutException:
                        star = "non-provided"
                    pack = {
                        'name': name,
                        'url': link,
                        'address': address,
                        'rating': rating,
                        'img': img,
                        'des': des,
                        'star': star
                    }
                    if any(val == '' for val in pack.values()):
                        raise StaleElementReferenceException
                    hotel_ls.append(pack)
                    print(f'{name}: success')
                try:
                    fetching()
                except StaleElementReferenceException:
                    for j in range(5):
                        try:
                            time.sleep(3)
                            print(f'fetching attempt {j}')
                            fetching()
                            break
                        except StaleElementReferenceException:
                            print(f'attempt {j} fail')
                            if j == 4:
                                with open('logs/agoda_lost_data.txt', 'a') as e:
                                    lnk = self.driver.current_url
                                    e.write(lnk)
                                print(f"lost data")
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            col.insert_many(hotel_ls)
            print(f'store successfully at {time.perf_counter()}')
            try:
                self.scroll_to_bottom()
                self.driver.find_element(By.ID, 'paginationNext').click()
            except NoSuchElementException:
                break

    def scroll_to_bottom(self):
        for _i in range(4):
            time.sleep(1)
            try:
                self.driver.execute_script("window.scrollTo(0, 50000)")
            except WebDriverException:
                pass
            time.sleep(1)


if __name__ == '__main__':
    with open('jsons/divisions.json') as d:
        divisions = json.load(d)
    ext = ['花蓮市', '台東市', '宜蘭市', '台南縣', '墾丁']
    divisions.extend(ext)
    job_queue = queue.Queue()
    for job_index in divisions:
        job_queue.put(job_index)
    workers = []
    worker_count = 2
    for i in range(worker_count):
        num = i+1
        driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=chrome_options)
        driver.delete_all_cookies()
        worker = Worker(num, driver)
        workers.append(worker)

    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()