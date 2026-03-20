import cv2
import os

MAX_FRAMES = 400   # target frames per person

def extract_frames(video_path, output_folder, person_name):

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    saved_count = 0

    while True:

        ret, frame = cap.read()

        if not ret or saved_count >= MAX_FRAMES:
            break

        if frame_count % 3 == 0:

            filename = f"{person_name}_{saved_count}.jpg"
            path = os.path.join(output_folder, filename)

            cv2.imwrite(path, frame)
            saved_count += 1

        frame_count += 1

    cap.release()

    print(person_name, "frames saved:", saved_count)


extract_frames("VIDEOS/mohith.mp4","DATASET/Mohith","mohith")
extract_frames("VIDEOS/uday.mp4","DATASET/Uday","uday")
extract_frames("VIDEOS/DIVYADHAR.mp4","DATASET/DIVYADHAR","DIVYADHAR")