"""
The following is a simple example evaluation method.

It is meant to run within a container.

To run it locally, you can call the following bash script:

  ./test_run.sh

This will start the evaluation, reads from ./test/input and outputs to ./test/output

To save the container and prep it for upload to Grand-Challenge.org you can call:

  ./save.sh

Any container that shows the same behavior will do, this is purely an example of how one COULD do it.

Happy programming!
"""
import json
from glob import glob
import numpy as np
import os
import SimpleITK
import random
from statistics import mean
from pathlib import Path
from pprint import pformat, pprint

import psutil

from helpers import run_prediction_processing, run_prediction_processing_parallel, listen_to_children_errors
from eval_nuclei import evaluate_files
from evaluate_tissue import calculate_dice_for_files, calculate_micro_dice_score_with_masks

docker = False

if docker:
    INPUT_DIRECTORY = Path("/input")
    OUTPUT_DIRECTORY = Path("/output")
    GROUND_TRUTH_NUCLEI_DIRECTORY = Path("/opt/app/ground_truth_nuclei_preliminary_10")
    GROUND_TRUTH_TISSUE_DIRECTORY = Path("/opt/app/ground_truth_tissue_preliminary")
    metrics_tissue_output = '/output/metrics_tissue.json'
else:
    INPUT_DIRECTORY = Path("test")
    OUTPUT_DIRECTORY = Path("output")
    GROUND_TRUTH_NUCLEI_DIRECTORY = Path("ground_truth_nuclei_preliminary_10")
    GROUND_TRUTH_TISSUE_DIRECTORY = Path("ground_truth_tissue_preliminary")
    metrics_tissue_output = 'output/metrics_tissue.json'

image_shape = [1024, 1024]


def process(job):
    """Processes a single algorithm job, looking at the outputs"""
    report = "Processing:\n"
    report += pformat(job)
    report += "\n"

    # Before we start, ensure we catch any child-process crashes
    listen_to_children_errors()

    # Get the location of the (.json) output file for the algorithm job
    location_nuclei_json = get_file_location(
            job_pk=job["pk"],
            values=job["outputs"],
            slug="melanoma-10-class-nuclei-segmentation",
        )
    location_tissue_tiff = get_file_location(
            job_pk=job["pk"],
            values=job["outputs"],
            slug="melanoma-tissue-mask-segmentation",
        )

    # Get the image name of the (.tif) input image
    inference_image = get_image_name(
            values=job["inputs"],
            slug="melanoma-whole-slide-image",
    )

    inference_pk = get_image_pk(
            values=job["outputs"],
            slug="melanoma-tissue-mask-segmentation",
    )

    # Get the ground truth files
    ground_truth_nuclei = str(GROUND_TRUTH_NUCLEI_DIRECTORY / f"{inference_image}").replace(".tif", "_nuclei.json")
    ground_truth_tissue = GROUND_TRUTH_TISSUE_DIRECTORY / inference_image

    # Evaluate nuclei
    prediction_nuclei = location_nuclei_json
    metrics_nuclei = evaluate_files(ground_truth_nuclei, prediction_nuclei)

    # Evaluate tissue
    prediction_tissue = str(location_tissue_tiff / inference_pk) + ".tif"
    metrics_tissue = calculate_dice_for_files(ground_truth_tissue, prediction_tissue, tuple(image_shape))

    combined_result = {
        "filename": inference_image,
        "nuclei_metrics": metrics_nuclei,
        "tissue_metrics": metrics_tissue
    }

    return combined_result


def main():
    input_files = print_inputs()
    tissue_file_mapping = {}
    metrics = {}
    predictions = read_predictions()

    # Populating the file-mapping dict
    for job in predictions:
        for output in job['outputs']:
            if output['interface']['slug'] == 'melanoma-tissue-mask-segmentation':
                tissue_file = output['image']['pk'] + ".tif"
                original_filename = job['inputs'][0]['image']['name']
                tissue_file_mapping[tissue_file] = original_filename

    # Print the mapping
    print("Tissue file mapping:")
    for tissue_file, original_filename in tissue_file_mapping.items():
        print(f"{tissue_file} -> {original_filename}")

    metrics["results"] = run_prediction_processing(fn=process, predictions=predictions)


    # Compute micro DICE separately (all masks are needed)
    input_tissue = [item for item in input_files if item.endswith('.tif')]
    dice_score_tissue = calculate_micro_dice_score_with_masks(GROUND_TRUTH_TISSUE_DIRECTORY,
                                                           input_tissue,
                                                           tuple(image_shape),
                                                           tissue_file_mapping)

    metrics["aggregates"] = {}
    metrics["aggregates"]["micro_dice_tissue"] = dice_score_tissue

    # Compute average metrics (macro F1-score for nuclei and average DICE for tissue)
    f1_scores_per_class = {}
    dice_scores_per_class = {}
    num_files = len(metrics['results'])
    for result in metrics['results']:
        nuclei_metrics = result['nuclei_metrics']
        tissue_metrics = result['tissue_metrics']
        for class_name, class_metrics in nuclei_metrics.items():
            if class_name not in ["micro", "macro"]:  # skip "micro" and "macro"
                if class_name not in f1_scores_per_class:  # initialize if not in dict
                    f1_scores_per_class[class_name] = 0
                f1_scores_per_class[class_name] += class_metrics['f1_score']
        for tissue_class, dice_score in tissue_metrics.items():
            if tissue_class not in dice_scores_per_class:
                dice_scores_per_class[tissue_class] = 0
            dice_scores_per_class[tissue_class] += dice_score

    # Compute the F1-score for each nuclei class
    for class_name in f1_scores_per_class:
        f1_scores_per_class[class_name] /= num_files
    metrics["aggregates"]["f1_nuclei"] = f1_scores_per_class

    # Compute overall macro F1-score by averaging the per-class F1-scores
    macro_f1 = np.mean(list(f1_scores_per_class.values()))
    metrics["aggregates"]["macro_f1_nuclei_average"] = macro_f1

    # Compute the average DICE score for each tissue class
    metrics["aggregates"]["dice_tissue"] = {}
    for tissue_class, total_score in dice_scores_per_class.items():
        avg_dice = total_score / num_files
        metrics["aggregates"]["dice_tissue"][tissue_class] = avg_dice

    write_metrics(metrics=metrics)

    return 0

def print_inputs():
    # Just for convenience, in the logs you can then see what files you have to work with
    input_files = [str(x) for x in Path(INPUT_DIRECTORY).rglob("*") if x.is_file()]

    print("Input Files:")
    pprint(input_files)
    print("")
    return input_files


def read_predictions():
    # The prediction file tells us the location of the users' predictions
    with open(INPUT_DIRECTORY / "predictions.json") as f:
        return json.loads(f.read())


def get_image_name(*, values, slug):
    # This tells us the user-provided name of the input or output image
    for value in values:
        if value["interface"]["slug"] == slug:
            return value["image"]["name"]

    raise RuntimeError(f"Image with interface {slug} not found!")


def get_image_pk(*, values, slug):
    # This tells us the user-provided name of the input or output image
    for value in values:
        if value["interface"]["slug"] == slug:
            return value["image"]["pk"]

    raise RuntimeError(f"Image with interface {slug} not found!")


def get_interface_relative_path(*, values, slug):
    # Gets the location of the interface relative to the input or output
    for value in values:
        if value["interface"]["slug"] == slug:
            return value["interface"]["relative_path"]

    raise RuntimeError(f"Value with interface {slug} not found!")


def get_file_location(*, job_pk, values, slug):
    # Where a job's output file will be located in the evaluation container
    relative_path = get_interface_relative_path(values=values, slug=slug)
    return INPUT_DIRECTORY / job_pk / "output" / relative_path


def load_json_file(*, location):
    # Reads a json file
    with open(location) as f:
        return json.loads(f.read())


def write_metrics(*, metrics):
        def convert(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.str_):
                return str(obj)
            else:
                return obj
        # Write a json document used for ranking results on the leaderboard
        with open(OUTPUT_DIRECTORY / "metrics.json", "w") as f:
            f.write(json.dumps(metrics, indent=4, default=convert))


if __name__ == "__main__":
    raise SystemExit(main())
