import cv2
import os

# Load face detector
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

input_dataset = "DATASET"
output_dataset = "CROPPED_DATASET"

people = ["Mohith", "Uday","DIVYADHAR"]

for person in people:

    input_path = os.path.join(input_dataset, person)
    output_path = os.path.join(output_dataset, person)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    count = 0

    for image_name in os.listdir(input_path):

        img_path = os.path.join(input_path, image_name)

        img = cv2.imread(img_path)

        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5
        )

        for (x, y, w, h) in faces:

            face = img[y:y+h, x:x+w]

            face = cv2.resize(face, (128,128))

            save_path = os.path.join(
                output_path,
                f"{person}_{count}.jpg"
            )

            cv2.imwrite(save_path, face)

            count += 1

    print(person, "faces saved:", count)