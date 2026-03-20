import cv2
import os
import numpy as np
import random


def augment_from_single_image(image_path, output_folder, target=2000):

    # create folder if not exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # read original image
    img = cv2.imread(image_path)

    if img is None:
        print("Image not found!")
        return

    print("Generating augmented images...")

    for i in range(target):

        aug = img.copy()

        choice = random.randint(0,8)

        # Flip Horizontal
        if choice == 0:
            aug = cv2.flip(aug,1)

        # Flip Vertical
        elif choice == 1:
            aug = cv2.flip(aug,0)

        # Rotation
        elif choice == 2:
            angle = random.randint(-25,25)
            h,w = aug.shape[:2]
            M = cv2.getRotationMatrix2D((w//2,h//2),angle,1)
            aug = cv2.warpAffine(aug,M,(w,h))

        # Brightness
        elif choice == 3:
            alpha = random.uniform(0.7,1.3)
            beta = random.randint(-40,40)
            aug = cv2.convertScaleAbs(aug,alpha=alpha,beta=beta)

        # Zoom
        elif choice == 4:
            h,w = aug.shape[:2]

            zoom = random.uniform(0.8,1.0)

            nh = int(h*zoom)
            nw = int(w*zoom)

            y = random.randint(0,h-nh)
            x = random.randint(0,w-nw)

            crop = aug[y:y+nh,x:x+nw]
            aug = cv2.resize(crop,(w,h))

        # Shift
        elif choice == 5:
            h,w = aug.shape[:2]

            M = np.float32([
                [1,0,random.randint(-20,20)],
                [0,1,random.randint(-20,20)]
            ])

            aug = cv2.warpAffine(aug,M,(w,h))

        # Noise
        elif choice == 6:
            noise = np.random.normal(0,25,aug.shape).astype(np.uint8)
            aug = cv2.add(aug,noise)

        # Blur
        elif choice == 7:
            aug = cv2.GaussianBlur(aug,(5,5),0)

        # Color change
        elif choice == 8:
            hsv = cv2.cvtColor(aug,cv2.COLOR_BGR2HSV)
            hsv[:,:,1] = hsv[:,:,1] * random.uniform(0.7,1.3)
            aug = cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)

        save_path = os.path.join(output_folder,f"img_{i}.jpg")

        cv2.imwrite(save_path,aug)

    print("Done! 2000 images saved in:", output_folder)



# ---------- RUN ----------

augment_from_single_image(
    "SAI.jpeg",
    "CROPPED_DATASET/SAI",
    2000
)