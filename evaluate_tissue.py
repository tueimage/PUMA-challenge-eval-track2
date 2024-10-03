import numpy as np
import os
from PIL import Image
import argparse
import json

def calculate_dice_from_masks(mask1, mask2, eps=0.00001):
    """Calculate the DICE score between two binary masks."""
    intersection = np.sum(mask1 & mask2)
    union = np.sum(mask1) + np.sum(mask2)

    dice_score = (2 * intersection + eps) / (union + eps)
    return dice_score

def calculate_dice_score_with_masks(tif1, tif2, image_shape, eps=0.00001):
    """Calculate the DICE score between two TIF files using masks."""
    tif1 = np.array(Image.open(tif1).resize(image_shape, Image.NEAREST))
    tif2 = np.array(Image.open(tif2).resize(image_shape, Image.NEAREST))

    dice_scores = {}
    class_map = {1: 'tissue_stroma', 2: 'tissue_blood_vessel', 3: 'tissue_tumor', 4: 'tissue_epidermis', 5: 'tissue_necrosis'}

    for category in range(1, 6):
        # Generate binary masks for each class
        mask1 = np.where(tif1 == category, 1, 0)
        mask2 = np.where(tif2 == category, 1, 0)

        # If both masks are empty, perfect match
        if np.sum(mask1) == 0 and np.sum(mask2) == 0:
            dice_score = 1.0
        else:
            dice_score = calculate_dice_from_masks(mask1, mask2, eps)

        dice_scores[class_map[category]] = dice_score

    return dice_scores

def calculate_micro_dice_score_with_masks(gt_folder, input_files, image_shape, file_mapping, eps=0.00001):
    """Calculate the overall micro DICE score across all classes between two folders of TIF masks."""
    class_map = {1: 'tissue_stroma', 2: 'tissue_blood_vessel', 3: 'tissue_tumor', 4: 'tissue_epidermis', 5: 'tissue_necrosis'}
    total_gt_mask = {class_name: [] for class_name in class_map.values()}  # Ground truth masks
    total_pred_mask = {class_name: [] for class_name in class_map.values()}  # Predicted masks

    # Loop through each common file and accumulate masks for each class
    for path in input_files:
        file = file_mapping[path.split('/')[-1]]
        gt_path = os.path.join(gt_folder, file)  # Ground truth mask path
        pred_path = path  # Predicted mask path

        gt_tif = np.array(Image.open(gt_path).resize(image_shape, Image.NEAREST))
        pred_tif = np.array(Image.open(pred_path).resize(image_shape, Image.NEAREST))

        for category, class_name in class_map.items():
            gt_mask = np.where(gt_tif == category, 1, 0)
            pred_mask = np.where(pred_tif == category, 1, 0)

            total_gt_mask[class_name].append(gt_mask)
            total_pred_mask[class_name].append(pred_mask)

    # Concatenate all masks for each class along the height axis (axis=1)
    for class_name in class_map.values():
        total_gt_mask[class_name] = np.concatenate(total_gt_mask[class_name], axis=0)
        total_pred_mask[class_name] = np.concatenate(total_pred_mask[class_name], axis=0)

    # Calculate the micro DICE score for each class using the giant arrays
    micro_dice_scores = {}
    for class_name in class_map.values():
        mask1 = total_gt_mask[class_name]
        mask2 = total_pred_mask[class_name]

        intersection = np.sum(mask1 & mask2)
        union = np.sum(mask1) + np.sum(mask2)

        dice_score = (2 * intersection + eps) / (union + eps)
        if intersection == 0:
            dice_score = 0.0

        micro_dice_scores[class_name] = dice_score
    average_dice_score = np.mean(list(micro_dice_scores.values()))
    micro_dice_scores['average_micro_dice'] = average_dice_score

    return micro_dice_scores

def calculate_dice_for_files(ground_truth_file, prediction_file, image_shape):
    """Calculate the DICE scores for a single ground truth and prediction file."""
    dice_scores = calculate_dice_score_with_masks(ground_truth_file, prediction_file, image_shape)

    # Calculate the average DICE score across all classes for this file
    class_scores = [score for score in dice_scores.values() if score is not None]
    average_dice = sum(class_scores) / len(class_scores) if class_scores else 0.0
    dice_scores['average_dice'] = average_dice

    return dice_scores

def main():
    pass

if __name__ == "__main__":
    main()
