# 12.databricks/notebooks/model_training_notebook.py
import logging
import os
import json # For dbutils.notebook.exit
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler, Imputer
from pyspark.ml.classification import RandomForestClassifier # Using RandomForest
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.sql.types import StringType

# --- Configuration Sourcing ---
# Configuration is sourced primarily from Databricks widgets if available,
# otherwise, it falls back to environment variables. This allows flexibility
# for running as a Databricks job or in other environments.

IS_DATABRICKS_ENV = False
try:
    # Attempt to use dbutils.widgets for Databricks job parameters
    dbutils.widgets.text("STORAGE_ACCOUNT_NAME", "", "Storage Account Name (e.g., yourstorageaccount)")
    dbutils.widgets.text("DATASETS_CONTAINER_NAME", "datasets", "Cleaned Datasets Container (e.g., datasets)")
    dbutils.widgets.text("MODELS_CONTAINER_NAME", "models", "Models Output Container (e.g., models)")
    # Storage key is optional; prefer Managed Identity, Service Principal, or AAD Passthrough
    dbutils.widgets.text("AZURE_STORAGE_ACCOUNT_KEY", "", "Azure Storage Account Key (Optional)")

    STORAGE_ACCOUNT_NAME = dbutils.widgets.get("STORAGE_ACCOUNT_NAME")
    DATASETS_CONTAINER_NAME = dbutils.widgets.get("DATASETS_CONTAINER_NAME")
    MODELS_CONTAINER_NAME = dbutils.widgets.get("MODELS_CONTAINER_NAME")
    AZURE_STORAGE_ACCOUNT_KEY = dbutils.widgets.get("AZURE_STORAGE_ACCOUNT_KEY") # Will be empty if not provided
    IS_DATABRICKS_ENV = True
    logging.info("Running in Databricks environment. Configuration sourced from widgets.")
except NameError: # dbutils is not defined
    logging.info("dbutils not found. Assuming non-Databricks environment. Sourcing configuration from environment variables.")
    STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
    DATASETS_CONTAINER_NAME = os.environ.get("DATASETS_CONTAINER_NAME") # Default can be set here if desired
    MODELS_CONTAINER_NAME = os.environ.get("MODELS_CONTAINER_NAME")
    AZURE_STORAGE_ACCOUNT_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY") # Will be None if not set

# --- Path Definitions ---
# Ensure core configuration is present before defining paths
if not STORAGE_ACCOUNT_NAME or not DATASETS_CONTAINER_NAME or not MODELS_CONTAINER_NAME:
    msg = "FATAL: STORAGE_ACCOUNT_NAME, DATASETS_CONTAINER_NAME, or MODELS_CONTAINER_NAME is not configured. " \
          "Ensure these are set via Databricks widgets or environment variables."
    logging.error(msg)
    if IS_DATABRICKS_ENV:
        dbutils.notebook.exit(json.dumps({"status": "Error", "message": msg}))
    raise ValueError(msg)

CLEANED_DATA_BASE_PATH = f"abfss://{DATASETS_CONTAINER_NAME}@{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/olist_cleaned_parquet/"
MODEL_OUTPUT_BASE_PATH = f"abfss://{MODELS_CONTAINER_NAME}@{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/customer_satisfaction_model/"

# --- Helper Functions ---
def get_spark_session():
    """Gets or creates a Spark session, configuring ADLS Gen2 access if an account key is provided."""
    spark_builder = SparkSession.builder.appName("OlistCustomerSatisfactionModelTraining")

    if STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY:
        # Configure Spark to access ADLS Gen2 using the provided account key.
        # This is one authentication method. In many Databricks setups, cluster-level
        # permissions (Managed Identity, Service Principal, AAD Passthrough) are preferred
        # and would make this explicit key configuration unnecessary.
        spark_builder.config(
            f"fs.azure.account.key.{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net",
            AZURE_STORAGE_ACCOUNT_KEY
        )
        logging.info(f"Configured Spark to access ADLS Gen2: {STORAGE_ACCOUNT_NAME} using account key.")
    elif STORAGE_ACCOUNT_NAME:
        # Account key not provided, but storage account name is.
        # Rely on other configured authentication methods for ADLS Gen2 access.
        logging.info(
            f"AZURE_STORAGE_ACCOUNT_KEY not provided for {STORAGE_ACCOUNT_NAME}. "
            "Spark access to ADLS Gen2 relies on other auth methods (e.g., Managed Identity, Service Principal, AAD Passthrough)."
        )
    # If STORAGE_ACCOUNT_NAME is not set, Spark won't be able to form ADLS paths correctly.
    # The check before path definitions should catch this.
    return spark_builder.getOrCreate()

def train_satisfaction_model(spark: SparkSession) -> dict:
    """
    Trains a customer satisfaction model using data from ADLS Gen2,
    evaluates it, and saves the trained pipeline model back to ADLS Gen2.
    Returns a dictionary containing the status, model path, and evaluation metrics.
    """
    logging.info("Starting Customer Satisfaction Model Training process.")

    try:
        # 1. Load Data
        # Assumes 'master_order_details' and 'order_reviews' Parquet files exist from a prior data transformation step.
        master_df_path = f"{CLEANED_DATA_BASE_PATH}master_order_details"
        reviews_df_path = f"{CLEANED_DATA_BASE_PATH}order_reviews"
        logging.info(f"Loading master order details from: {master_df_path}")
        master_df = spark.read.parquet(master_df_path)
        logging.info(f"Loading order reviews from: {reviews_df_path}")
        reviews_df = spark.read.parquet(reviews_df_path)

        # 2. Feature Engineering: Join data and define the target variable
        # Select only necessary columns from reviews_df to avoid ambiguity after join.
        data_df = master_df.join(reviews_df.select("order_id", "review_score"), "order_id", "inner")
        
        # Target variable 'satisfaction_label': 1 for satisfied (score 4 or 5), 0 otherwise.
        # Rows with null 'review_score' are dropped as the target cannot be determined.
        data_df = data_df.na.drop(subset=["review_score"])
        data_df = data_df.withColumn("satisfaction_label",
                                     when(col("review_score") >= 4, 1).otherwise(0))
        
        logging.info("Target variable 'satisfaction_label' created.")
        data_df.groupBy("satisfaction_label").count().show(truncate=False)

        # 3. Feature Selection & Preprocessing Pipeline Stages
        # Define categorical and numerical features to be used in the model.
        # 'product_category_name_english' is expected to be created during data transformation.
        categorical_cols_to_use = [
            "payment_type",
            "product_category_name_english",
            "customer_state"
        ]
        numerical_cols_to_use = [
            "price", "freight_value", "payment_installments", "payment_value",
            "product_name_length", "product_description_length", "product_photos_qty",
            "product_weight_g", "product_length_cm", "product_width_cm", "product_height_cm"
        ]

        # Robustness: Check for column existence and handle missing 'product_category_name_english'.
        if "product_category_name_english" not in data_df.columns:
            logging.warning("'product_category_name_english' not found. "
                            "Attempting to use 'product_category_name' as fallback or 'unknown'. "
                            "Ensure data transformation step correctly creates this column.")
            if "product_category_name" in data_df.columns:
                 data_df = data_df.withColumn("product_category_name_english", col("product_category_name"))
            else:
                 data_df = data_df.withColumn("product_category_name_english", lit("unknown").cast(StringType()))

        # Filter selected columns to only those present in the DataFrame.
        final_categorical_cols = [c for c in categorical_cols_to_use if c in data_df.columns]
        final_numerical_cols = [c for c in numerical_cols_to_use if c in data_df.columns]
        
        logging.info(f"Final selected categorical features: {final_categorical_cols}")
        logging.info(f"Final selected numerical features: {final_numerical_cols}")

        if not final_categorical_cols and not final_numerical_cols:
            msg = "No valid features selected after checking column existence. Aborting model training."
            logging.error(msg)
            if IS_DATABRICKS_ENV:
                dbutils.notebook.exit(json.dumps({"status": "Error", "message": msg}))
            raise ValueError(msg)

        pipeline_stages = []

        # Numerical feature imputation
        imputed_numerical_output_cols = []
        if final_numerical_cols:
            imputed_numerical_output_cols = [f"{c}_imputed" for c in final_numerical_cols]
            num_imputer = Imputer(
                inputCols=final_numerical_cols,
                outputCols=imputed_numerical_output_cols,
                strategy="mean" # Using mean; median is another common choice.
            )
            pipeline_stages.append(num_imputer)

        # Categorical feature processing: Impute nulls, StringIndex, OneHotEncode
        ohe_output_cols = []
        for cat_col in final_categorical_cols:
            # Impute nulls in categorical columns with a placeholder string *before* StringIndexer.
            # This must be done on the DataFrame directly, not as a pipeline stage before StringIndexer
            # if StringIndexer's handleInvalid is 'error'. Using 'keep' can also work around this.
            data_df = data_df.fillna("Unknown_Category_Placeholder", subset=[cat_col])
            
            idx_output_col = cat_col + "_idx"
            ohe_col = cat_col + "_ohe"
            ohe_output_cols.append(ohe_col)

            string_indexer = StringIndexer(inputCol=cat_col, outputCol=idx_output_col, handleInvalid="keep")
            one_hot_encoder = OneHotEncoder(inputCols=[idx_output_col], outputCols=[ohe_col])
            pipeline_stages += [string_indexer, one_hot_encoder]

        # Assemble all features into a single vector
        assembler_inputs = imputed_numerical_output_cols + ohe_output_cols
        if not assembler_inputs:
            msg = "No features available for VectorAssembler. Check preprocessing steps."
            logging.error(msg)
            if IS_DATABRICKS_ENV:
                dbutils.notebook.exit(json.dumps({"status": "Error", "message": msg}))
            raise ValueError(msg)
            
        vector_assembler = VectorAssembler(inputCols=assembler_inputs, outputCol="features")
        pipeline_stages.append(vector_assembler)

        # 4. Define Model (Random Forest Classifier)
        # RandomForest is often a good general-purpose classifier.
        rf_classifier = RandomForestClassifier(
            featuresCol="features",
            labelCol="satisfaction_label",
            numTrees=100, # Number of trees in the forest
            maxDepth=5,   # Maximum depth of each tree
            seed=42       # For reproducibility
        )
        pipeline_stages.append(rf_classifier)

        # 5. Create and Configure Pipeline
        pipeline = Pipeline(stages=pipeline_stages)

        # 6. Split data into training and test sets
        train_df, test_df = data_df.randomSplit([0.8, 0.2], seed=42) # 80% training, 20% testing
        logging.info(f"Training data count: {train_df.count()}, Test data count: {test_df.count()}")
        train_df.persist() # Cache training data for faster iterations if memory allows
        test_df.persist()  # Cache test data

        # 7. Train model using the defined pipeline
        logging.info("Starting model training with the configured pipeline...")
        pipeline_model = pipeline.fit(train_df)
        logging.info("Model training complete.")

        # 8. Make predictions on the test set and evaluate model performance
        predictions_df = pipeline_model.transform(test_df)

        # Evaluate using Area Under ROC (for binary classification)
        evaluator_auc = BinaryClassificationEvaluator(
            labelCol="satisfaction_label",
            rawPredictionCol="rawPrediction", # Default output col for probabilities/raw scores
            metricName="areaUnderROC"
        )
        auc = evaluator_auc.evaluate(predictions_df)
        logging.info(f"Area Under ROC (AUC) on Test Set: {auc:.4f}")

        # Evaluate using Accuracy
        evaluator_accuracy = MulticlassClassificationEvaluator( # Binary is a subset of Multiclass
            labelCol="satisfaction_label",
            predictionCol="prediction", # Default output col for final predictions
            metricName="accuracy"
        )
        accuracy = evaluator_accuracy.evaluate(predictions_df)
        logging.info(f"Accuracy on Test Set: {accuracy:.4f}")
        
        logging.info("Confusion Matrix on Test Set:")
        predictions_df.groupBy("satisfaction_label", "prediction").count().orderBy("satisfaction_label", "prediction").show(truncate=False)

        train_df.unpersist() # Release cached data
        test_df.unpersist()

        # 9. Save the trained pipeline model
        # The entire pipeline (including preprocessing steps) is saved.
        logging.info(f"Saving trained pipeline model to: {MODEL_OUTPUT_BASE_PATH}")
        pipeline_model.write().overwrite().save(MODEL_OUTPUT_BASE_PATH)
        logging.info("Pipeline model saved successfully to ADLS Gen2.")

        # Prepare results dictionary
        training_results = {
            "status": "Success",
            "model_path": MODEL_OUTPUT_BASE_PATH,
            "metrics": {
                "auc": auc,
                "accuracy": accuracy
            },
            "features_used": {
                "categorical": final_categorical_cols,
                "numerical": final_numerical_cols
            }
        }
        if IS_DATABRICKS_ENV:
            # Exit notebook with a JSON string for Databricks job orchestration
            dbutils.notebook.exit(json.dumps(training_results))
        return training_results

    except Exception as e:
        logging.error(f"An error occurred during model training: {e}", exc_info=True)
        error_payload = {"status": "Error", "message": str(e)}
        if IS_DATABRICKS_ENV:
            dbutils.notebook.exit(json.dumps(error_payload))
        raise # Re-raise exception for non-Databricks job environments or direct runs

# --- Main execution block ---
# This allows the script to be run directly (e.g., for testing)
# or imported as a module.
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    
    # Reminder for non-Databricks execution:
    if not IS_DATABRICKS_ENV:
        print("Running in a non-Databricks environment.")
        if not all([STORAGE_ACCOUNT_NAME, DATASETS_CONTAINER_NAME, MODELS_CONTAINER_NAME]):
            print("WARNING: STORAGE_ACCOUNT_NAME, DATASETS_CONTAINER_NAME, or MODELS_CONTAINER_NAME "
                  "environment variables are not fully set. ADLS Gen2 access might fail.")
            print("Please ensure these are correctly configured for your execution environment.")
        if STORAGE_ACCOUNT_NAME and not AZURE_STORAGE_ACCOUNT_KEY:
            print("WARNING: AZURE_STORAGE_ACCOUNT_KEY is not set. "
                  "Ensure your environment has appropriate permissions (e.g., CLI login, Managed Identity) "
                  "to access the specified Azure Storage Account.")

    spark = None
    try:
        spark = get_spark_session()
        result = train_satisfaction_model(spark)
        logging.info(f"Model Training Script Finished. Result: {result}")
    except Exception as main_exc:
        logging.error(f"Critical error in main execution block: {main_exc}", exc_info=True)
    finally:
        if spark and not IS_DATABRICKS_ENV:
            # Stop Spark session only if not in Databricks and session was created
            # In Databricks, the cluster manages the Spark session lifecycle.
            logging.info("Stopping Spark session for non-Databricks environment.")
            spark.stop()
        elif spark and IS_DATABRICKS_ENV:
            logging.info("Spark session managed by Databricks. Not stopping explicitly.")