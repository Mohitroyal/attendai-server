import os
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from sklearn.model_selection import train_test_split

# ================= CONFIG =================

DATASET_DIR = "CROPPED_DATASET"
MODEL_PATH = "model/face_model4.keras"

IMG_SIZE = 128
BATCH_SIZE = 32
EPOCHS = 20

# IMPORTANT: dataset order
label_names = ["DIVYADHAR", "Mohith", "Uday"]

os.makedirs("model", exist_ok=True)

# ================= LOAD DATASET =================

print("\nLoading dataset...")

images = []
labels = []

for label_idx, person in enumerate(label_names):

    folder = os.path.join(DATASET_DIR, person)

    count = 0

    for img_name in os.listdir(folder):

        path = os.path.join(folder, img_name)

        img = cv2.imread(path)

        if img is None:
            continue

        img = cv2.resize(img, (IMG_SIZE, IMG_SIZE))

        images.append(img)
        labels.append(label_idx)

        count += 1

    print(person, "images:", count)

images = np.array(images) / 255.0
labels = np.array(labels)

print("Total images:", len(images))

# ================= SPLIT DATA =================

X_train, X_val, y_train, y_val = train_test_split(
    images,
    labels,
    test_size=0.2,
    random_state=42,
    stratify=labels
)

print("Train:", len(X_train))
print("Validation:", len(X_val))

# ================= DATA AUGMENTATION =================

datagen = ImageDataGenerator(
    rotation_range=10,
    width_shift_range=0.05,
    height_shift_range=0.05,
    zoom_range=0.05,
    horizontal_flip=True
)

datagen.fit(X_train)

# ================= MODEL =================

print("\nBuilding model...")

model = models.Sequential([

    layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3)),

    layers.Conv2D(32, (3,3), activation='relu'),
    layers.MaxPooling2D(),

    layers.Conv2D(64, (3,3), activation='relu'),
    layers.MaxPooling2D(),

    layers.Conv2D(128, (3,3), activation='relu'),
    layers.MaxPooling2D(),

    layers.Flatten(),

    layers.Dense(128, activation='relu'),
    layers.Dropout(0.5),

    layers.Dense(len(label_names), activation='softmax')

])

model.summary()

# ================= COMPILE =================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0003),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# ================= CALLBACKS =================

callbacks = [

    EarlyStopping(
        monitor='val_accuracy',
        patience=5,
        restore_best_weights=True
    ),

    ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=3
    ),

    ModelCheckpoint(
        MODEL_PATH,
        monitor='val_accuracy',
        save_best_only=True
    )

]

# ================= TRAIN =================

print("\nTraining started...\n")

history = model.fit(

    datagen.flow(X_train, y_train, batch_size=BATCH_SIZE),

    steps_per_epoch=len(X_train)//BATCH_SIZE,

    epochs=EPOCHS,

    validation_data=(X_val, y_val),

    callbacks=callbacks
)

# ================= SAVE MODEL =================

model.save(MODEL_PATH)

print("\nModel saved to:", MODEL_PATH)
print("Labels:", label_names)