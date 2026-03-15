# Morrisons Case Study: Meeting Customers’ Expectations with Real-Time Data Insights

Morrisons, one of the UK’s largest supermarkets, serves nine million customers weekly across 500 supermarkets and 1,600 Morrisons Daily stores. To maintain its commitment to fresh produce and innovation, Morrisons modernized its data stack by migrating from an on-premise system to Google Cloud.

## The Challenge
Previously, Morrisons' data for reporting and machine learning (ML) forecasting was stored in an on-premise database. Due to security restrictions, this data had to be exported before use, leading to reports being produced on a daily basis. This meant that teams were always working with data that was at least 24 hours behind the real world, making it difficult to optimize operations or build real-time algorithms.

## The Solution
Morrisons migrated its data to **BigQuery** and integrated it with **Looker** for business intelligence. They also utilized **Vertex AI** for ML modeling and **Gemini** for generative AI capabilities.

### Key Components:
- **BigQuery:** Serves as the central, scalable data warehouse for all business data, including real-time sales feeds from every store.
- **Looker:** Provides a semantic reporting layer that allows employees across the business to access insights without needing to write complex queries.
- **Vertex AI:** Used by ML engineers to build forecasting models for product sales, customer preferences, and network optimization.
- **Gemini & NotebookLM:** Used to summarize customer sentiment trends and convert reports into audio files for on-the-go employees.
- **Cloud Run Functions:** Power the "Product Finder" tool in the Morrisons app, processing searches in real-time.

## Key Results
- **98.96% Reduction in Data Lag:** Reporting lag was reduced from one day to just 15 minutes.
- **Real-Time Inventory Management:** Store managers can now see exact product availability in real-time, enabling more accurate ordering and stocking.
- **Improved Customer Experience:** The "Product Finder" tool receives 50,000 hits daily, helping customers locate items in-store, even when layouts change for seasonal promotions.
- **Enhanced Strategic Decision-Making:** Accurate ML models now help optimize the logistics network, reducing the number of miles driven annually.

## Conclusion
By modernizing its data infrastructure with Google Cloud, Morrisons has transformed from a daily reporting cycle to a real-time, data-driven operation. This shift has empowered both data scientists and business colleagues to solve complex problems and deliver better service to millions of customers.

> "The difference between then and now is like night and day. When we started, our data scientists had to wait to access the data each day. Now, not only can the data scientist access it in real time, our business colleagues can too. That’s all been made possible by Google Cloud."
> 
> — **Peter Laflin**, Chief Data Officer, Morrisons
