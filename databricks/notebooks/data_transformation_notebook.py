# 12.databricks/notebooks/data_transformation_notebook.py
import logging
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, lower, trim, regexp_replace, when
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType, FloatType

# --- Configuration ---
# These configurations should be sourced from environment variables.
# For Azure Functions, set these in the Function App's configuration.
# For Databricks jobs, use job parameters or cluster environment variables.

STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
RAW_DATA_CONTAINER = os.environ.get("RAW_DATA_CONTAINER_NAME")
DATASETS_CONTAINER = os.environ.get("DATASETS_CONTAINER_NAME")
# AZURE_STORAGE_ACCOUNT_KEY is required if using account key authentication.
# In production, prefer Service Principal, Managed Identity, or AAD passthrough.
# Ensure this secret is handled securely (e.g., Databricks secrets, Azure Key Vault).
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")


BASE_INPUT_PATH_TEMPLATE = f"abfss://{RAW_DATA_CONTAINER}@{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/"
BASE_OUTPUT_PATH_TEMPLATE = f"abfss://{DATASETS_CONTAINER}@{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/olist_cleaned_parquet/"

# --- Helper Functions ---
def get_spark_session():
    """Gets or creates a Spark session."""
    spark = SparkSession.builder.appName("OlistDataCleaning").getOrCreate()

    # Configure Spark to access Azure Data Lake Storage Gen2 if an account key is provided.
    # This is one method of authentication; others (Service Principal, Managed Identity)
    # might be configured at the cluster level in Databricks and wouldn't require this explicit key.
    if STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY:
        spark.conf.set(
            f"fs.azure.account.key.{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net",
            AZURE_STORAGE_ACCOUNT_KEY
        )
        logging.info(f"Configured Spark to access ADLS Gen2: {STORAGE_ACCOUNT_NAME} using account key.")
    elif STORAGE_ACCOUNT_NAME: # Key not provided, but account name is.
        logging.warning(
            f"AZURE_STORAGE_ACCOUNT_KEY not set for {STORAGE_ACCOUNT_NAME}. "
            "Spark access to ADLS Gen2 relies on other auth methods (e.g., cluster-level AAD passthrough or Service Principal)."
        )
    else:
        logging.warning("STORAGE_ACCOUNT_NAME not set. Spark may not be able to access ADLS Gen2.")
    return spark

def clean_column_names(df):
    """
    Cleans DataFrame column names:
    - Converts to lowercase.
    - Replaces spaces and hyphens with underscores.
    - Removes other non-alphanumeric characters (except underscore).
    """
    for old_col_name in df.columns:
        new_col_name = old_col_name.lower().replace(" ", "_").replace("-", "_")
        # Keep only alphanumeric characters and underscores
        new_col_name = regexp_replace(new_col_name, r"[^a-zA-Z0-9_]", "")
        df = df.withColumnRenamed(old_col_name, new_col_name)
    return df

# --- Schemas ---
# Explicitly defining schemas is crucial for:
# 1. Robustness: Prevents type inference errors with CSVs.
# 2. Performance: Spark can optimize reads better with a known schema.
# 3. Data Integrity: Enforces expected data types.

customers_schema = StructType([
    StructField("customer_id", StringType(), True),
    StructField("customer_unique_id", StringType(), True),
    StructField("customer_zip_code_prefix", StringType(), True), # Kept as string for leading zeros
    StructField("customer_city", StringType(), True),
    StructField("customer_state", StringType(), True),
])

geolocation_schema = StructType([
    StructField("geolocation_zip_code_prefix", StringType(), True),
    StructField("geolocation_lat", DoubleType(), True),
    StructField("geolocation_lng", DoubleType(), True),
    StructField("geolocation_city", StringType(), True),
    StructField("geolocation_state", StringType(), True),
])

orders_schema = StructType([
    StructField("order_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("order_status", StringType(), True),
    StructField("order_purchase_timestamp", TimestampType(), True),
    StructField("order_approved_at", TimestampType(), True),
    StructField("order_delivered_carrier_date", TimestampType(), True),
    StructField("order_delivered_customer_date", TimestampType(), True),
    StructField("order_estimated_delivery_date", TimestampType(), True),
])

order_items_schema = StructType([
    StructField("order_id", StringType(), True),
    StructField("order_item_id", IntegerType(), True),
    StructField("product_id", StringType(), True),
    StructField("seller_id", StringType(), True),
    StructField("shipping_limit_date", TimestampType(), True),
    StructField("price", FloatType(), True),
    StructField("freight_value", FloatType(), True),
])

order_payments_schema = StructType([
    StructField("order_id", StringType(), True),
    StructField("payment_sequential", IntegerType(), True),
    StructField("payment_type", StringType(), True),
    StructField("payment_installments", IntegerType(), True),
    StructField("payment_value", FloatType(), True),
])

order_reviews_schema = StructType([
    StructField("review_id", StringType(), True),
    StructField("order_id", StringType(), True),
    StructField("review_score", IntegerType(), True),
    StructField("review_comment_title", StringType(), True),
    StructField("review_comment_message", StringType(), True),
    StructField("review_creation_date", TimestampType(), True),
    StructField("review_answer_timestamp", TimestampType(), True),
])

products_schema = StructType([
    StructField("product_id", StringType(), True),
    StructField("product_category_name", StringType(), True),
    StructField("product_name_lenght", IntegerType(), True), # Original dataset has a typo
    StructField("product_description_lenght", IntegerType(), True), # Original dataset has a typo
    StructField("product_photos_qty", IntegerType(), True),
    StructField("product_weight_g", IntegerType(), True),
    StructField("product_length_cm", IntegerType(), True),
    StructField("product_width_cm", IntegerType(), True),
    StructField("product_height_cm", IntegerType(), True),
])

sellers_schema = StructType([
    StructField("seller_id", StringType(), True),
    StructField("seller_zip_code_prefix", StringType(), True),
    StructField("seller_city", StringType(), True),
    StructField("seller_state", StringType(), True),
])

category_name_translation_schema = StructType([
    StructField("product_category_name", StringType(), True),
    StructField("product_category_name_english", StringType(), True),
])

# Defines the datasets to process: (source_filename, schema_variable, target_output_name)
DATASETS_TO_PROCESS = [
    ("olist_customers_dataset.csv", customers_schema, "customers"),
    ("olist_geolocation_dataset.csv", geolocation_schema, "geolocation"),
    ("olist_orders_dataset.csv", orders_schema, "orders"),
    ("olist_order_items_dataset.csv", order_items_schema, "order_items"),
    ("olist_order_payments_dataset.csv", order_payments_schema, "order_payments"),
    ("olist_order_reviews_dataset.csv", order_reviews_schema, "order_reviews"),
    ("olist_products_dataset.csv", products_schema, "products"),
    ("olist_sellers_dataset.csv", sellers_schema, "sellers"),
    ("product_category_name_translation.csv", category_name_translation_schema, "category_translation"),
]


def process_dataset(spark, filename, schema, output_name, input_base_path, output_base_path):
    """Reads a CSV dataset, applies cleaning transformations, and writes it as Parquet."""
    input_path = input_base_path + filename
    output_path = output_base_path + output_name

    logging.info(f"Processing {filename} from {input_path}")
    try:
        # Read CSV with specified schema and timestamp format. inferSchema=False is important for performance and robustness.
        df = spark.read.csv(input_path, header=True, schema=schema, inferSchema=False, timestampFormat="yyyy-MM-dd HH:mm:ss")
    except Exception as e:
        logging.error(f"Error reading CSV {input_path}: {e}")
        # A more robust path check might involve Hadoop FileSystem APIs,
        # but for simplicity, we rely on Spark's error if the path is invalid.
        raise # Re-raise the original exception to halt processing for this file.

    # 1. Standardize column names
    df = clean_column_names(df)

    # 2. Trim whitespace from all string columns and convert empty strings to null
    string_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, StringType)]
    for s_col in string_cols:
        df = df.withColumn(s_col, trim(col(s_col)))
        df = df.withColumn(s_col, when(col(s_col) == "", None).otherwise(col(s_col)))

    # 3. Apply dataset-specific cleaning logic
    if output_name == "products":
        # Correct typos in column names from the original dataset
        if "product_name_lenght" in df.columns:
             df = df.withColumnRenamed("product_name_lenght", "product_name_length")
        if "product_description_lenght" in df.columns:
             df = df.withColumnRenamed("product_description_lenght", "product_description_length")
        # Impute null product_category_name with 'unknown' for consistency
        df = df.withColumn("product_category_name",
                           when(col("product_category_name").isNull(), "unknown")
                           .otherwise(col("product_category_name")))

    if output_name == "orders":
        # Standardize order_status to lowercase
        df = df.withColumn("order_status", lower(col("order_status")))

    if output_name == "geolocation":
        # Geolocation data can have multiple entries for the same zip code.
        # Here, we simply drop exact duplicates across all relevant fields.
        # More advanced strategies might involve averaging lat/lng per zip or taking the first entry.
        df = df.dropDuplicates(['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng', 'geolocation_city', 'geolocation_state'])

    # 4. Drop exact duplicate rows across the entire DataFrame after initial cleaning
    df = df.dropDuplicates()

    # Write the cleaned DataFrame to Parquet format, overwriting if it exists
    logging.info(f"Writing cleaned data for {output_name} to {output_path}")
    df.write.mode("overwrite").parquet(output_path)
    logging.info(f"Successfully wrote {output_name} to Parquet.")
    return df # Return DataFrame for potential downstream use (e.g., joins)


def perform_full_olist_transformation(spark_session: SparkSession,
                                      input_base_path: str,
                                      output_base_path: str) -> str:
    """
    Orchestrates the cleaning of all Olist datasets and optionally creates a master table.
    Returns the output path on success, or an error message on failure.
    """
    logging.info("Starting Olist data transformation with PySpark.")

    # Critical check for storage configuration
    if not all([STORAGE_ACCOUNT_NAME, RAW_DATA_CONTAINER, DATASETS_CONTAINER]):
        msg = "FATAL: STORAGE_ACCOUNT_NAME, RAW_DATA_CONTAINER, or DATASETS_CONTAINER environment variables are not set."
        logging.error(msg)
        raise ValueError(msg) # Fail fast if core config is missing

    # Authentication check (warning, as other methods might be in place)
    # This check assumes account key is the primary method if explicit config is needed by the script.
    # `spark.conf.get` with a default `None` checks if the key was set by `get_spark_session` or already existed.
    spark_conf_key = f"fs.azure.account.key.{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net"
    if not AZURE_STORAGE_ACCOUNT_KEY and not spark_session.conf.get(spark_conf_key, None):
        logging.warning(
            f"AZURE_STORAGE_ACCOUNT_KEY is not set and no account key seems configured in Spark session for {STORAGE_ACCOUNT_NAME}. "
            "Access might fail if not using other auth methods (e.g., Service Principal, Managed Identity, AAD Passthrough on cluster)."
        )

    all_dfs = {} # To store processed DataFrames for potential joining
    for filename, schema, output_name in DATASETS_TO_PROCESS:
        try:
            df = process_dataset(spark_session, filename, schema, output_name, input_base_path, output_base_path)
            all_dfs[output_name] = df
        except Exception as e:
            # If any dataset fails, log the error and report failure for the entire transformation.
            # Depending on requirements, one might choose to continue with other datasets.
            logging.error(f"Failed to process dataset {filename}: {e}", exc_info=True)
            return f"ERROR: Failed during processing of {filename}. Check logs. Partial output might be at {output_base_path}"

    # --- Optional: Create a denormalized master table by joining key datasets ---
    # This is a common step for preparing data for Machine Learning.
    try:
        required_dfs_for_join = ["orders", "order_items", "products", "customers", "category_translation"]
        if all(k in all_dfs for k in required_dfs_for_join):
            logging.info("Attempting to join key datasets to create a master_order_details table...")
            orders_df = all_dfs["orders"]
            order_items_df = all_dfs["order_items"]
            products_df = all_dfs["products"]
            customers_df = all_dfs["customers"]
            category_df = all_dfs["category_translation"]

            # Enrich products with English category names
            products_enriched_df = products_df.join(
                category_df,
                products_df.product_category_name == category_df.product_category_name, # Join condition
                "left" # Keep all products, even if no translation
            ).drop(category_df.product_category_name) # Drop redundant column from category_df

            # Build the master table step-by-step
            order_details_df = orders_df.join(order_items_df, "order_id", "inner") # Only orders with items
            order_details_df = order_details_df.join(products_enriched_df, "product_id", "left") # Add product details
            master_df = order_details_df.join(customers_df, "customer_id", "left") # Add customer details

            master_output_path = output_base_path + "master_order_details"
            logging.info(f"Writing master_order_details table to {master_output_path}")
            master_df.write.mode("overwrite").parquet(master_output_path)
            logging.info("Master_order_details table written successfully.")
        else:
            logging.warning("Skipping master table creation as not all required DataFrames were processed successfully.")
    except Exception as e:
        # Log join errors but don't necessarily make the whole ETL fail if individual tables were fine.
        logging.error(f"Error during join operations to create master table: {e}", exc_info=True)

    logging.info(f"All Olist data transformations complete. Cleaned data (Parquet) is in: {output_base_path}")
    return output_base_path # Success: return the base path of cleaned Parquet datasets


def perform_basic_data_transformation(raw_data_str: str, blob_name: str) -> str:
    """
    Entry point intended to be called by an Azure Function or similar trigger mechanism.
    The `raw_data_str` and `blob_name` are typically from a trigger (e.g., queue message content, blob name).
    This function orchestrates the full Olist ETL, reading from configured ADLS paths.
    """
    logging.info(f"[DatabricksSparkETL] Received trigger (blob_name: {blob_name}). Starting full Olist ETL.")
    # raw_data_str is usually ignored if the ETL processes fixed datasets as done here.
    # logging.info(f"[DatabricksSparkETL] Raw data string length (typically ignored): {len(raw_data_str)}")

    spark = None
    try:
        spark = get_spark_session()
        # Construct paths based on environment variables (assumed to be set)
        input_path = f"abfss://{RAW_DATA_CONTAINER}@{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/"
        output_path = f"abfss://{DATASETS_CONTAINER}@{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/olist_cleaned_parquet/"

        # Spark's write.mode("overwrite") will typically create the output directory if it doesn't exist.
        # Explicit directory creation (e.g., with dbutils.fs.mkdirs) is often not needed for Parquet writes.

        result_message = perform_full_olist_transformation(spark, input_path, output_path)
        return result_message # This will be the path to the cleaned data directory or an error message.

    except Exception as e:
        logging.error(f"[DatabricksSparkETL] Critical error during Spark ETL: {e}", exc_info=True)
        return f"ERROR: Spark ETL failed. Details: {str(e)}" # Return an error message for the caller.
    finally:
        if spark:
            # In a managed Databricks environment, `spark.stop()` is usually not necessary or desired
            # as the Spark session is managed by the cluster.
            # If running this script in a self-managed Spark environment (e.g., local, or a custom setup
            # where an Azure Function creates and manages the SparkSession), then `spark.stop()` would be appropriate.
            # spark.stop()
            logging.info("[DatabricksSparkETL] Spark processing finished (session not explicitly stopped in this context).")

# --- Main execution block for local testing or direct script run ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not all([os.environ.get("STORAGE_ACCOUNT_NAME"),
                os.environ.get("RAW_DATA_CONTAINER_NAME"),
                os.environ.get("DATASETS_CONTAINER_NAME")]):
        print("FATAL: Please set STORAGE_ACCOUNT_NAME, RAW_DATA_CONTAINER_NAME, and DATASETS_CONTAINER_NAME environment variables.")
        print("If using account key auth, also set AZURE_STORAGE_ACCOUNT_KEY.")
    else:
        print(f"Attempting to run ETL with settings from environment variables:")
        print(f"  Storage Account: {os.environ['STORAGE_ACCOUNT_NAME']}")
        print(f"  Raw Data Container: {os.environ['RAW_DATA_CONTAINER_NAME']}")
        print(f"  Datasets Container: {os.environ['DATASETS_CONTAINER_NAME']}")
        if os.environ.get("AZURE_STORAGE_ACCOUNT_KEY"):
            print("  AZURE_STORAGE_ACCOUNT_KEY is set (value masked).")
        else:
            print("  AZURE_STORAGE_ACCOUNT_KEY is NOT set (relying on other auth methods if applicable).")

        # The "dummy_raw_data" and "trigger_file.txt" are placeholders,
        # as this ETL reads predefined datasets based on environment config.
        output_status = perform_basic_data_transformation("dummy_raw_data_payload", "trigger_file.txt")
        print(f"\nETL Run Status/Output Location: {output_status}")