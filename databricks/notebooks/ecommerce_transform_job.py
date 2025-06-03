# ./databricks/notebooks/ecommerce_transform_job.py

# --- Import necessary PySpark modules ---
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lower, trim, regexp_replace, to_timestamp, date_format,
    year, month, dayofmonth, when, sum, avg, count, first,
    lit, coalesce, upper, initcap,  # initcap for proper casing of cities
    round as spark_round # Alias round to avoid conflict with Python's built-in round
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
import re # For regular expressions used in column name cleaning
import json # For dbutils.notebook.exit to return structured output

print("Starting Olist ETL Transformation Job in Databricks Notebook...")

# ---------------------------------------------------------------------------
# 0. Get Parameters and Initialize Spark Session
# These parameters are passed from the Azure Function orchestrator.
# ---------------------------------------------------------------------------
# Define widgets to accept parameters if run interactively,
# or they will be picked up if passed via API call.
dbutils.widgets.text("input_file_name", "olist_daily_trigger", "Contextual trigger info (e.g., date or specific file if applicable)")
dbutils.widgets.text("raw_data_container", "raw-data", "Name of the raw data Azure Storage container")
dbutils.widgets.text("processed_data_container", "processed-data", "Name of the processed data Azure Storage container")
dbutils.widgets.text("storage_account_name", "", "Azure Storage Account Name")

# Retrieve parameter values
trigger_context_info = dbutils.widgets.get("input_file_name")
raw_container_name = dbutils.widgets.get("raw_data_container")
processed_container_name = dbutils.widgets.get("processed_data_container")
storage_account_name_param = dbutils.widgets.get("storage_account_name")

# Log retrieved parameters for verification
print(f"Trigger Context: {trigger_context_info}")
print(f"Raw Data Container: {raw_container_name}")
print(f"Processed Data Container: {processed_container_name}")
print(f"Storage Account Name: {storage_account_name_param}")

# Validate essential parameters
if not all([raw_container_name, processed_container_name, storage_account_name_param]):
    error_message = "Critical Error: Missing one or more required parameters (raw_data_container, processed_data_container, storage_account_name)."
    print(error_message)
    dbutils.notebook.exit(json.dumps({"status": "failed", "error": error_message, "details": "Essential ADLS paths not configured."}))

# Initialize SparkSession
spark = SparkSession.builder.appName(f"Olist_ETL_Transform_Job_{trigger_context_info}").getOrCreate()
print(f"Spark session initialized. Spark version: {spark.version}")

# --- Define Base Paths for ADLS Gen2 ---
# Assumes Olist CSV files are directly in a subfolder (e.g., 'olist_dataset') under the raw container, or directly in the raw container.
# Adjust 'olist_dataset_source_folder' if your files are in a different sub-directory or at the root.
olist_dataset_source_folder = "" # e.g., "olist_source_files" or "" if files are at the root of raw_container_name
base_adls_input_path = f"abfss://{raw_container_name}@{storage_account_name_param}.dfs.core.windows.net/{olist_dataset_source_folder}".rstrip('/')
# Output will be stored in a dedicated folder within the processed container
base_adls_output_path = f"abfss://{processed_container_name}@{storage_account_name_param}.dfs.core.windows.net/olist_ecommerce_processed"

print(f"Base ADLS Input Path: {base_adls_input_path}")
print(f"Base ADLS Output Path: {base_adls_output_path}")

# ---------------------------------------------------------------------------
# 1. Helper Functions
# ---------------------------------------------------------------------------
def clean_column_names(df_to_clean):
    """Cleans and standardizes DataFrame column names to snake_case."""
    cleaned_columns = []
    for current_col_name in df_to_clean.columns:
        new_name = str(current_col_name).lower() # Convert to string and lowercase
        new_name = re.sub(r'[^\w_]', '', re.sub(r'\s+', '_', new_name)) # Replace spaces with underscores, remove non-alphanumeric (except _)
        new_name = re.sub(r'_+', '_', new_name) # Replace multiple underscores with a single one
        new_name = new_name.strip('_') # Remove leading/trailing underscores
        cleaned_columns.append(new_name)
    return df_to_clean.toDF(*cleaned_columns)

def read_olist_csv(csv_file_name, custom_schema=None, infer_schema_setting=True, header_setting=True):
    """Reads a specific Olist CSV file, cleans column names, and handles potential read errors."""
    full_path = f"{base_adls_input_path}/{csv_file_name}"
    print(f"Attempting to read CSV: {full_path}")
    
    reader_options = spark.read.format("csv").option("header", str(header_setting).lower())
    if custom_schema:
        reader_options = reader_options.schema(custom_schema)
    else:
        reader_options = reader_options.option("inferSchema", str(infer_schema_setting).lower())
    
    try:
        df = reader_options.load(full_path)
        df = clean_column_names(df) # Apply column name cleaning
        row_count = df.count() # Get row count for logging
        print(f"Successfully read '{csv_file_name}'. Row count: {row_count}. Schema:")
        df.printSchema()
        df.show(3, truncate=False) # Show a few rows for quick inspection
        return df
    except Exception as e:
        error_detail = f"Failed to read CSV '{csv_file_name}' from path '{full_path}'. Error: {str(e)}"
        print(f"CRITICAL ERROR: {error_detail}")
        # dbutils.notebook.exit(json.dumps({"status": "failed", "error": error_detail}))
        raise # Re-raise the exception to mark the Databricks job as failed

def write_df_to_parquet(df_to_write, target_subfolder, partition_columns=None):
    """Writes a DataFrame to Parquet format in the specified output subfolder, with optional partitioning."""
    output_path = f"{base_adls_output_path}/{target_subfolder}"
    print(f"Writing DataFrame to Parquet at: {output_path} (Partitioned by: {partition_columns if partition_columns else 'None'})")
    
    writer = df_to_write.write.mode("overwrite").format("parquet")
    if partition_columns:
        if isinstance(partition_columns, str): # Handle single string or list of strings
            partition_columns = [partition_columns]
        writer = writer.partitionBy(*partition_columns)
    
    try:
        writer.save(output_path)
        print(f"Successfully wrote Parquet data to {output_path}")
    except Exception as e:
        error_detail = f"Failed to write Parquet for '{target_subfolder}' to path '{output_path}'. Error: {str(e)}"
        print(f"CRITICAL ERROR: {error_detail}")
        # dbutils.notebook.exit(json.dumps({"status": "failed", "error": error_detail}))
        raise

# ---------------------------------------------------------------------------
# 2. Read and Perform Initial Cleaning for Each Olist Dataset
# ---------------------------------------------------------------------------
print("\n--- Section 2: Reading and Initial Cleaning of Individual Datasets ---")

# Customers Dataset
customers_df = read_olist_csv("olist_customers_dataset.csv")
customers_df = customers_df.dropDuplicates(['customer_id']) # customer_id is the PK
customers_df = customers_df.withColumn("customer_city", trim(initcap(lower(col("customer_city"))))) # Standardize city names
customers_df = customers_df.withColumn("customer_state", upper(trim(col("customer_state")))) # Standardize state codes

# Geolocation Dataset (can be large, aggregate to reduce size and denormalize)
geolocation_df = read_olist_csv("olist_geolocation_dataset.csv", infer_schema_setting=True) # Infer schema, but be mindful of types
geolocation_agg_df = geolocation_df.groupBy("geolocation_zip_code_prefix") \
    .agg(
        spark_round(avg("geolocation_lat"), 5).alias("geo_latitude"), # Average lat/lng, rounded
        spark_round(avg("geolocation_lng"), 5).alias("geo_longitude"),
        first("geolocation_city").alias("geo_city_name"), # Take the first city/state (may need refinement)
        first("geolocation_state").alias("geo_state_code")
    )
geolocation_agg_df = geolocation_agg_df.withColumn("geo_city_name", trim(initcap(lower(col("geo_city_name")))))
geolocation_agg_df = geolocation_agg_df.withColumn("geo_state_code", upper(trim(col("geo_state_code"))))

# Orders Dataset
orders_df = read_olist_csv("olist_orders_dataset.csv")
timestamp_columns_orders = [
    "order_purchase_timestamp", "order_approved_at",
    "order_delivered_carrier_date", "order_delivered_customer_date",
    "order_estimated_delivery_date"
]
for ts_col in timestamp_columns_orders:
    orders_df = orders_df.withColumn(ts_col, to_timestamp(col(ts_col)))
orders_df = orders_df.withColumn("order_purchase_year", year(col("order_purchase_timestamp"))) # For partitioning
orders_df = orders_df.withColumn("order_purchase_month", month(col("order_purchase_timestamp"))) # For partitioning
orders_df = orders_df.withColumn("order_status", lower(trim(col("order_status")))) # Standardize order status

# Order Items Dataset
order_items_df = read_olist_csv("olist_order_items_dataset.csv")
order_items_df = order_items_df.withColumn("shipping_limit_date", to_timestamp(col("shipping_limit_date")))
order_items_df = order_items_df.withColumn("price", col("price").cast(DoubleType())) # Ensure numeric types
order_items_df = order_items_df.withColumn("freight_value", col("freight_value").cast(DoubleType()))

# Order Payments Dataset
order_payments_df = read_olist_csv("olist_order_payments_dataset.csv")
order_payments_df = order_payments_df.withColumn("payment_value", col("payment_value").cast(DoubleType()))
order_payments_df = order_payments_df.withColumn("payment_type", lower(trim(regexp_replace(col("payment_type"), "_", " ")))) # Clean payment types

# Order Reviews Dataset (Handle schema carefully due to text fields)
# Explicit schema definition for reviews is safer than inferring.
olist_review_schema = StructType([
    StructField("review_id", StringType(), True), StructField("order_id", StringType(), True),
    StructField("review_score", StringType(), True), # Read as string then cast, robust to non-numeric
    StructField("review_comment_title", StringType(), True), StructField("review_comment_message", StringType(), True),
    StructField("review_creation_date", StringType(), True), StructField("review_answer_timestamp", StringType(), True)
])
order_reviews_df = read_olist_csv("olist_order_reviews_dataset.csv", custom_schema=olist_review_schema, header_setting=True)
order_reviews_df = order_reviews_df.withColumn("review_score", col("review_score").cast(IntegerType())) # Cast score to integer
timestamp_columns_reviews = ["review_creation_date", "review_answer_timestamp"]
for ts_col in timestamp_columns_reviews:
    order_reviews_df = order_reviews_df.withColumn(ts_col, to_timestamp(col(ts_col)))

# Products Dataset
products_df = read_olist_csv("olist_products_dataset.csv")
numeric_product_cols = [ # Ensure these are numeric and handle nulls
    "product_name_lenght", "product_description_lenght", "product_photos_qty",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"
]
for num_col in numeric_product_cols:
    products_df = products_df.withColumn(num_col, col(num_col).cast(DoubleType()))
    products_df = products_df.fillna(0, subset=[num_col]) # Fill nulls with 0 or another appropriate value
products_df = products_df.withColumn("product_category_name", lower(trim(col("product_category_name"))))

# Sellers Dataset
sellers_df = read_olist_csv("olist_sellers_dataset.csv")
sellers_df = sellers_df.dropDuplicates(['seller_id']) # seller_id is the PK
sellers_df = sellers_df.withColumn("seller_city", trim(initcap(lower(col("seller_city")))))
sellers_df = sellers_df.withColumn("seller_state", upper(trim(col("seller_state"))))

# Product Category Name Translation Dataset
category_translation_df = read_olist_csv("product_category_name_translation.csv")
category_translation_df = category_translation_df.withColumn("product_category_name", lower(trim(col("product_category_name"))))
category_translation_df = category_translation_df.withColumn("product_category_name_english", lower(trim(col("product_category_name_english"))))
category_translation_df = category_translation_df.dropDuplicates(['product_category_name']) # Ensure unique Portuguese names for joining

# ---------------------------------------------------------------------------
# 3. Translate Product Category Names
# ---------------------------------------------------------------------------
print("\n--- Section 3: Translating Product Category Names to English ---")
products_translated_df = products_df.join(
    category_translation_df, "product_category_name", "left_outer" # Use left_outer to keep all products
)
# Use English name if available, otherwise fallback to original Portuguese name
products_translated_df = products_translated_df.withColumn(
    "category_name_en",
    coalesce(col("product_category_name_english"), col("product_category_name")) # Fallback logic
).drop("product_category_name", "product_category_name_english") # Drop original and intermediate translation columns
products_translated_df.select("product_id", "category_name_en").show(5, truncate=False)

# ---------------------------------------------------------------------------
# 4. Join DataFrames to Create a Comprehensive Fact Table for Orders
# This involves joining orders, items, payments, products, customers, sellers, and geolocation.
# ---------------------------------------------------------------------------
print("\n--- Section 4: Assembling the Main 'Fact Orders' DataFrame ---")

# Start with orders and join order_items (one order can have multiple items)
fact_orders_df = orders_df.join(order_items_df, "order_id", "inner") # Inner join as items are essential to an order line
print(f"Fact Orders: Count after joining orders + items: {fact_orders_df.count()}")

# Aggregate payment information per order (an order might have multiple payment lines)
order_payment_summary_df = order_payments_df.groupBy("order_id") \
    .agg(
        spark_round(sum("payment_value"), 2).alias("total_order_payment_value"),
        max(col("payment_installments")).alias("max_payment_installments_count"),
        first("payment_type").alias("primary_order_payment_type") # Simplification: take the first payment type
    )
fact_orders_df = fact_orders_df.join(order_payment_summary_df, "order_id", "left_outer")
print(f"Fact Orders: Count after joining payment summary: {fact_orders_df.count()}")

# Join with translated product information
fact_orders_df = fact_orders_df.join(products_translated_df.alias("prod_info"), "product_id", "left_outer")
fact_orders_df = fact_orders_df.withColumnRenamed("category_name_en", "product_category_english") # Rename for clarity
print(f"Fact Orders: Count after joining product info: {fact_orders_df.count()}")

# Join with customer information
fact_orders_df = fact_orders_df.join(customers_df.alias("cust_info"), "customer_id", "left_outer")
print(f"Fact Orders: Count after joining customer info: {fact_orders_df.count()}")

# Join with seller information
fact_orders_df = fact_orders_df.join(sellers_df.alias("sell_info"), "seller_id", "left_outer")
print(f"Fact Orders: Count after joining seller info: {fact_orders_df.count()}")

# Join with customer geolocation data (using customer_zip_code_prefix)
fact_orders_df = fact_orders_df.join(
    geolocation_agg_df.alias("cust_geo_info"),
    fact_orders_df["customer_zip_code_prefix"] == col("cust_geo_info.geolocation_zip_code_prefix"),
    "left_outer"
).drop(col("cust_geo_info.geolocation_zip_code_prefix")) \
 .withColumnRenamed("geo_latitude", "customer_geo_latitude") \
 .withColumnRenamed("geo_longitude", "customer_geo_longitude") \
 .withColumnRenamed("geo_city_name", "customer_geo_city") \
 .withColumnRenamed("geo_state_code", "customer_geo_state")
print(f"Fact Orders: Count after joining customer geolocation: {fact_orders_df.count()}")

# Join with seller geolocation data (using seller_zip_code_prefix)
fact_orders_df = fact_orders_df.join(
    geolocation_agg_df.alias("sell_geo_info"),
    fact_orders_df["seller_zip_code_prefix"] == col("sell_geo_info.geolocation_zip_code_prefix"),
    "left_outer"
).drop(col("sell_geo_info.geolocation_zip_code_prefix")) \
 .withColumnRenamed("geo_latitude", "seller_geo_latitude") \
 .withColumnRenamed("geo_longitude", "seller_geo_longitude") \
 .withColumnRenamed("geo_city_name", "seller_geo_city") \
 .withColumnRenamed("geo_state_code", "seller_geo_state")
print(f"Fact Orders: Count after joining seller geolocation: {fact_orders_df.count()}")

# --- Select and Alias Final Columns for the Fact Table ---
# This defines the final structure of your main orders fact table.
final_fact_orders_columns = [
    col("order_id"),
    col("cust_info.customer_id").alias("customer_id"), # Alias to avoid ambiguity if column exists in orders_df
    col("cust_info.customer_unique_id").alias("customer_unique_id"),
    col("order_item_id"), # From order_items_df
    col("product_id"),   # From order_items_df
    col("sell_info.seller_id").alias("seller_id"),     # Alias from sellers_df
    col("order_status"),
    col("order_purchase_timestamp"),
    col("order_purchase_year"), # Derived column
    col("order_purchase_month"),# Derived column
    col("order_approved_at"),
    col("order_delivered_carrier_date"),
    col("order_delivered_customer_date"),
    col("order_estimated_delivery_date"),
    col("shipping_limit_date"), # From order_items_df
    col("price").alias("item_price"), # From order_items_df
    col("freight_value").alias("item_freight_value"), # From order_items_df
    col("total_order_payment_value"), # From payment_summary
    col("max_payment_installments_count").alias("max_payment_installments"), # Renamed from payment_summary
    col("primary_order_payment_type"), # From payment_summary
    col("prod_info.product_category_english").alias("product_category_name"), # From products_translated_df
    col("prod_info.product_weight_g"), col("prod_info.product_length_cm"),
    col("prod_info.product_height_cm"), col("prod_info.product_width_cm"),
    col("cust_info.customer_zip_code_prefix").alias("customer_zip_code_prefix"),
    col("cust_info.customer_city").alias("customer_city_name"), # Renamed from customers_df
    col("cust_info.customer_state").alias("customer_state_code"), # Renamed from customers_df
    col("customer_geo_latitude"), col("customer_geo_longitude"),
    col("customer_geo_city").alias("customer_geolocation_city"), # Renamed from geolocation join
    col("customer_geo_state").alias("customer_geolocation_state"), # Renamed from geolocation join
    col("sell_info.seller_zip_code_prefix").alias("seller_zip_code_prefix"),
    col("sell_info.seller_city").alias("seller_city_name"), # Renamed from sellers_df
    col("sell_info.seller_state").alias("seller_state_code"), # Renamed from sellers_df
    col("seller_geo_latitude"), col("seller_geo_longitude"),
    col("seller_geo_city").alias("seller_geolocation_city"), # Renamed from geolocation join
    col("seller_geo_state").alias("seller_geolocation_state") # Renamed from geolocation join
]
fact_orders_final_df = fact_orders_df.select(final_fact_orders_columns)

print("Final 'Fact Orders' Table Schema:")
fact_orders_final_df.printSchema()
fact_orders_final_df.show(3, truncate=False)
final_row_count = fact_orders_final_df.count()
print(f"Final 'Fact Orders' Table Row Count: {final_row_count}")


# ---------------------------------------------------------------------------
# 5. Write Processed DataFrames to Parquet in ADLS Gen2
# This includes the main fact table and individual dimension tables.
# ---------------------------------------------------------------------------
print("\n--- Section 5: Writing Processed DataFrames to Parquet Storage ---")

# Write the main fact_orders table, partitioned by year and month for query optimization
write_df_to_parquet(fact_orders_final_df, "fact_orders", partition_columns=["order_purchase_year", "order_purchase_month"])

# Write individual dimension tables (cleaned and potentially enriched)
# Dimension: Products (with translated category names)
dim_products_df = products_translated_df.select(
    "product_id",
    col("category_name_en").alias("product_category_name"), # Use the translated name
    "product_name_lenght", "product_description_lenght", "product_photos_qty",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"
)
write_df_to_parquet(dim_products_df, "dim_products")

# Dimension: Customers
dim_customers_df = customers_df.select(
    "customer_id", "customer_unique_id", "customer_zip_code_prefix",
    "customer_city", "customer_state"
)
write_df_to_parquet(dim_customers_df, "dim_customers")

# Dimension: Sellers
dim_sellers_df = sellers_df.select(
    "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"
)
write_df_to_parquet(dim_sellers_df, "dim_sellers")

# Dimension: Geolocation (aggregated)
dim_geolocation_df = geolocation_agg_df.withColumnRenamed("geolocation_zip_code_prefix", "zip_code_prefix") \
    .select("zip_code_prefix", "geo_latitude", "geo_longitude", "geo_city_name", "geo_state_code")
write_df_to_parquet(dim_geolocation_df, "dim_geolocation")

# Dimension: Order Reviews (cleaned)
# You might want to select specific columns or further process review text
dim_order_reviews_df = order_reviews_df.select(
    "review_id", "order_id", "review_score",
    "review_comment_title", "review_comment_message", # Be mindful of PII if these are sensitive
    "review_creation_date", "review_answer_timestamp"
)
write_df_to_parquet(dim_order_reviews_df, "dim_order_reviews")


print("\n--- Olist ETL Transformation Job in Databricks Notebook Completed Successfully! ---")

# --- Return a success message and key metrics to the calling Azure Function ---
# This allows the orchestrator to know the outcome and potentially use output details.
output_payload = {
    "status": "success",
    "message": "Olist data successfully processed and transformed.",
    "output_base_path": base_adls_output_path,
    "fact_orders_table_path": f"{base_adls_output_path}/fact_orders",
    "fact_orders_row_count": final_row_count,
    "dimensions_created": ["dim_products", "dim_customers", "dim_sellers", "dim_geolocation", "dim_order_reviews"]
}
dbutils.notebook.exit(json.dumps(output_payload))