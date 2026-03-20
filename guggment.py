import cv2
import os
import numpy as np
import random

def augment_images(folder, target=1000):

    if not os.path.exists(folder):
        print("❌ Folder not found:", folder)
        return

    images = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg','.jpeg','.png'))]

    count = len(images)

    if count == 0:
        print("❌ No images in:", folder)
        return

    print(f"{folder} starting images: {count}")

    while count < target:

        img_name = random.choice(images)
        img_path = os.path.join(folder, img_name)

        img = cv2.imread(img_path)

        if img is None:
            continue

        aug = img.copy()

        transform = random.randint(0,4)

        # Flip
        if transform == 0:
            aug = cv2.flip(aug,1)

        # Rotation
        elif transform == 1:
            angle = random.randint(-20,20)
            h,w = aug.shape[:2]
            M = cv2.getRotationMatrix2D((w//2,h//2),angle,1)
            aug = cv2.warpAffine(aug,M,(w,h))

        # Brightness
        elif transform == 2:
            value = random.randint(-40,40)
            aug = cv2.convertScaleAbs(aug, alpha=1, beta=value)

        # Zoom
        elif transform == 3:
            h,w = aug.shape[:2]
            crop = aug[int(h*0.1):int(h*0.9), int(w*0.1):int(w*0.9)]
            aug = cv2.resize(crop,(w,h))

        # Shift
        elif transform == 4:
            h,w = aug.shape[:2]
            M = np.float32([[1,0,random.randint(-15,15)],
                            [0,1,random.randint(-15,15)]])
            aug = cv2.warpAffine(aug,M,(w,h))

        new_name = f"aug_{count}.jpg"

        cv2.imwrite(os.path.join(folder,new_name), aug)

        images.append(new_name)   # add new image to dataset
        count += 1

        if count % 100 == 0:
            print(folder, "generated:", count)

    print(f"✅ {folder} balanced to {count} images")


# Run for each person
augment_images("CROPPED_DATASET/Mohith",1000)
augment_images("CROPPED_DATASET/Uday",1000)
augment_images("CROPPED_DATASET/DIVYADHAR",1000)