import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import random
import streamlit as st
from time import sleep
import zipfile
import os

# List of user agents for random selection
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
]

# Directory to save the HTML files
html_directory = "saved_serp_html"

# Create the directory if it doesn't exist
if not os.path.exists(html_directory):
    os.makedirs(html_directory)

def search_google(tld, country, language, result_per_page, queries, domain_to_find, save_html=False, stop_on_domain_found=False):
    results_list = []
    
    for query in queries:
        st.write(f"Searching for: {query.strip()}")
        encoded_query = quote_plus(query.strip())
        google_url = f"https://www.{tld}/search?q={encoded_query}&gl={country}&hl={language}&num={result_per_page}&pws=0"
        
        attempts = 0
        delay = 5  # Starting delay for backoff
        while attempts < 3:
            try:
                headers = {"User-Agent": random.choice(user_agents)}
                response = requests.get(google_url, headers=headers)
                
                # Check for 429 response
                if response.status_code == 429:
                    st.warning("Too many requests. Pausing for a few seconds before retrying.")
                    sleep(delay)
                    attempts += 1
                    delay *= 2  # Exponential backoff
                    continue

                response.raise_for_status()

                # Save the HTML content if user opted in
                if save_html:
                    html_path = os.path.join(html_directory, f"{query.strip().replace(' ', '_')}_SERP.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    st.write(f"SERP HTML saved at: {html_path}")

                # Parse HTML response with BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                search_results = soup.select("div.g")
                
                snippet_type = None
                snippet_div = soup.find("div", class_="yp1CPe wDYxhc NFQFxe viOShc LKPcQc")
                if snippet_div:
                    if snippet_div.find("div", class_="di3YZe"):
                        snippet_type = "List type featured snippet"
                    elif snippet_div.find("div", class_="LGOjhe", attrs={"data-attrid": "wa:/description"}):
                        snippet_type = "Paragraph Featured Snippet"
                    elif snippet_div.find("div", class_="webanswers-webanswers_table__webanswers-table"):
                        snippet_type = "Table Featured Snippet"

                processed_urls = set()
                position = 0

                for result in search_results:
                    link_element = result.select_one("a[href]")
                    if link_element:
                        link = link_element.get("href")
                        if link not in processed_urls:
                            processed_urls.add(link)
                            position += 1
                            h3_element = result.select_one("h3")
                            title = h3_element.get_text() if h3_element else "No title"
                            domain_found = "Yes" if domain_to_find and domain_to_find in link else "No"
                            results_list.append({
                                "Query": query,
                                "Position": position,
                                "Domain Found": domain_found,
                                "Title": title,
                                "Link": link,
                                "Snippet Type": snippet_type if position == 1 else '',
                                "SERP HTML": html_path if save_html else "Not saved"
                            })

                            # Stop processing if domain is found and stop_on_domain_found is True
                            if stop_on_domain_found and domain_found == "Yes":
                                break

                st.write(f"Google Search URL: {google_url}")

                # Add a fixed 18-second delay before moving to the next query
                sleep(18)
                break  # Exit retry loop if successful

            except requests.exceptions.RequestException as e:
                st.error(f"Request error: {e}")
                break

    # Convert results list to DataFrame if not empty
    if results_list:
        results_df = pd.DataFrame(results_list)
        results_df = results_df[["Query", "Position", "Domain Found", "Title", "Link", "Snippet Type", "SERP HTML"]]
        st.session_state.results_df = results_df
    else:
        st.warning("No results were fetched. Please try adjusting your settings or waiting before retrying.")
        results_df = pd.DataFrame()  # Return empty DataFrame if no results

    return results_df

def create_zip_of_html_files(directory):
    zip_filename = "serp_html_files.zip"
    
    # Create a zip file containing all the HTML files
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for foldername, subfolders, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zipf.write(file_path, os.path.relpath(file_path, directory))
    
    return zip_filename

# Streamlit App Execution
if __name__ == "__main__":
    st.title("Google Search Scraper & Rank Tracker")

    # Option to choose between Google result scrapper and Rank Tracker
    task_type = st.radio("Select Task Type:", ("Google result scrapper", "Rank Tracker"))

    # Streamlit UI for inputs
    tld = st.text_input("Enter Google Domain (e.g., google.com):", "google.com")
    country = st.text_input("Enter the country code (e.g., 'in' for India):", "in")
    language = st.text_input("Enter the preferred language (e.g., 'en' for English):", "en")
    result_per_page = st.text_input("Enter the number of results per page:", "10")
    queries = st.text_area("Enter the list of keywords separated by commas:", "").split(",")
    save_html = st.checkbox("Save SERP HTML for each query?", False)  # Option to save SERP HTML

    # For Rank Tracker, provide domain to track
    if task_type == "Rank Tracker":
        domain_to_find = st.text_input("Enter the domain name you want to track:", "")
        stop_on_domain_found = True
    else:
        domain_to_find = ""
        stop_on_domain_found = False

    if st.button("Search"):
        if not queries:
            st.warning("Please provide the queries to search!")
        elif task_type == "Rank Tracker" and not domain_to_find:
            st.warning("Please provide the domain name to track!")
        else:
            search_results_df = search_google(tld, country, language, result_per_page, queries, domain_to_find, save_html, stop_on_domain_found)
            st.success("Search completed!")

    if 'results_df' in st.session_state and not st.session_state.results_df.empty:
        # Display "Results where domain found" filter only if task type is "Rank Tracker"
        if task_type == "Rank Tracker":
            filtered_df = st.session_state.results_df[st.session_state.results_df["Domain Found"] == "Yes"]
        else:
            # Show all results directly for Google result scrapper
            filtered_df = st.session_state.results_df

        st.write("Search Results:")
        st.dataframe(filtered_df)

        file_format = st.selectbox("Choose file format for download:", ("CSV", "Excel"))
        if file_format == "CSV":
            st.download_button("Download results as CSV", data=filtered_df.to_csv(index=False), mime="text/csv", file_name="search_results.csv")
        else:
            st.download_button("Download results as Excel", data=filtered_df.to_excel(index=False), mime="application/vnd.ms-excel", file_name="search_results.xlsx")
        
        # Provide option to download all saved SERP HTML files as a ZIP file
        if save_html:
            zip_file = create_zip_of_html_files(html_directory)
            with open(zip_file, "rb") as f:
                st.download_button(
                    label="Download all SERP HTML files as ZIP",
                    data=f,
                    file_name=zip_file,
                    mime="application/zip"
                )

        # Add a button to reset and run the app again if needed
        if st.button("Run Another Search"):
            st.session_state.clear()  # Clear the session state to allow for a fresh search
            st.rerun()  # Rerun the Streamlit app to start fresh