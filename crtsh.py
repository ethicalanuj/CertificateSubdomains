import requests
from bs4 import BeautifulSoup
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class crtShClass():

    def __init__(self, domains, output_file, num_threads):
        self.domains = domains
        self.output_file = output_file
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0'}
        self.cookies = {}
        self.foundURLsList = []
        self.timeout = 30
        self.retries = 5
        self.num_threads = num_threads

    def subdomainScrape(self, domain):
        url = f"https://crt.sh/?q=%25.{domain}"
        for attempt in range(self.retries):
            try:
                r = requests.get(url, headers=self.headers, timeout=self.timeout)
                r.raise_for_status()
                soup = BeautifulSoup(r.content, 'html.parser')

                tableRows = soup.find_all('table')[2].find_all('tr')

                subdomains = []
                for row in tableRows:
                    try:
                        subdomain = row.find_all('td')[4].text
                        subdomain = subdomain.replace("*.", "")
                        if subdomain not in self.foundURLsList:
                            subdomains.append(subdomain)
                    except Exception as e:
                        pass
                return subdomains
            except requests.RequestException as e:
                logging.error(f"Error fetching data for {domain}: {e}")
                if e.response and e.response.status_code == 503:
                    wait_time = 2 ** attempt
                    logging.info(f"503 Error: Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    if attempt < self.retries - 1:
                        wait_time = 5  # Wait for 5 seconds before retrying other errors
                        logging.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"Failed to fetch data for {domain} after {self.retries} attempts")
                        return []
        return []

    def run(self):
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_domain = {executor.submit(self.subdomainScrape, domain): domain for domain in self.domains}
            for future in as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    subdomains = future.result()
                    if subdomains:
                        self.foundURLsList.extend(subdomains)
                except Exception as e:
                    logging.error(f"Exception for domain {domain}: {e}")

    def saveSubdomains(self):
        unique_subdomains = list(set(self.foundURLsList))
        try:
            if os.path.isdir(self.output_file):
                logging.error(f"Output path '{self.output_file}' is a directory. Please provide a valid file path.")
                return
            if not os.path.exists(os.path.dirname(self.output_file)) and os.path.dirname(self.output_file) != '':
                os.makedirs(os.path.dirname(self.output_file))
            with open(self.output_file, 'w') as f:
                for subdomain in unique_subdomains:
                    f.write(subdomain + '\n')
            logging.info(f"Subdomains saved to {self.output_file}")
        except Exception as e:
            logging.error(f"Error saving subdomains to '{self.output_file}': {e}")

def read_domains_from_file(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f.readlines()]

def main():
    parser = argparse.ArgumentParser(description="Fetch subdomains for given domains using crt.sh")
    parser.add_argument("-d", "--domains", nargs='+', help="Domain Names; e.g., example.com example2.com")
    parser.add_argument("-i", "--input", help="Input file containing list of domains")
    parser.add_argument("-o", "--output", help="Output file to save the subdomains", required=True)
    parser.add_argument("-t", "--threads", type=int, default=5, help="Number of threads to use for concurrent requests (default: 5)")
    args = parser.parse_args()

    domains = []
    if args.input:
        domains.extend(read_domains_from_file(args.input))
    if args.domains:
        domains.extend(args.domains)

    if not domains:
        logging.error("No domains provided. Use -d or --domains to specify domains or -i or --input to specify an input file.")
        return

    crtsh = crtShClass(domains, args.output, args.threads)
    crtsh.run()
    crtsh.saveSubdomains()

if __name__ == "__main__":
    main()