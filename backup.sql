-- MySQL dump 10.13  Distrib 8.0.36, for Win64 (x86_64)
--
-- Host: localhost    Database: attendance_system
-- ------------------------------------------------------
-- Server version	8.0.36

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `admin`
--

DROP TABLE IF EXISTS `admin`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `admin` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `department` varchar(100) DEFAULT NULL,
  `email` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `admin`
--

LOCK TABLES `admin` WRITE;
/*!40000 ALTER TABLE `admin` DISABLE KEYS */;
INSERT INTO `admin` VALUES (4,'development@gmail.com','Admin@123','Development','development@gmail.com'),(7,'hr@gmail.com','hr','HR','hr@gmail.com');
/*!40000 ALTER TABLE `admin` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `attendance`
--

DROP TABLE IF EXISTS `attendance`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `attendance` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) DEFAULT NULL,
  `date` date DEFAULT NULL,
  `week` int DEFAULT NULL,
  `checkin` time DEFAULT NULL,
  `checkout` time DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `attendance`
--

LOCK TABLES `attendance` WRITE;
/*!40000 ALTER TABLE `attendance` DISABLE KEYS */;
INSERT INTO `attendance` VALUES (1,'Mohith','2026-03-08',10,'18:07:22','18:09:31'),(2,'Uday','2026-03-08',10,'18:25:16','18:30:37'),(3,'Mohith','2026-03-09',11,'08:42:54','20:25:45'),(4,'Uday','2026-03-10',11,'10:01:22','12:28:24'),(5,'Mohith','2026-03-10',11,'12:27:53','12:28:18'),(6,'Mohith','2026-03-12',11,'17:57:17','18:03:16'),(7,'Mohith','2026-03-13',11,'17:12:14',NULL),(8,'Mohith','2026-03-20',12,'18:05:59','18:12:50');
/*!40000 ALTER TABLE `attendance` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `employees`
--

DROP TABLE IF EXISTS `employees`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `employees` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) DEFAULT NULL,
  `department` varchar(100) DEFAULT 'General',
  `company_id` varchar(50) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `employees`
--

LOCK TABLES `employees` WRITE;
/*!40000 ALTER TABLE `employees` DISABLE KEYS */;
INSERT INTO `employees` VALUES (1,'Mohith','mohith@company.com','Mohith@123','Development','PVI25M011','2026-03-08 13:08:26'),(2,'Uday','uday@company.com','scrypt:32768:8:1$6xpOHTv5XoOLF170$46a368872dfc5bf0751082bc7a85fa4954bc4b0709af7655cddba2fe4bbb960d05dc2cdf13276694c252ab174e3643cf86a0761e7143c7712c3b08d85d8aaf56','Cybersecurity','PVI25M012','2026-03-08 13:08:26');
/*!40000 ALTER TABLE `employees` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `performance_log`
--

DROP TABLE IF EXISTS `performance_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `performance_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `employee_id` int NOT NULL,
  `action` varchar(50) DEFAULT NULL,
  `points` float DEFAULT NULL,
  `reason` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `performance_log`
--

LOCK TABLES `performance_log` WRITE;
/*!40000 ALTER TABLE `performance_log` DISABLE KEYS */;
INSERT INTO `performance_log` VALUES (1,1,'proof_rejected',-15,'Proof rejected: dddd. jdffn','2026-03-20 20:06:03');
/*!40000 ALTER TABLE `performance_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `performance_scores`
--

DROP TABLE IF EXISTS `performance_scores`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `performance_scores` (
  `id` int NOT NULL AUTO_INCREMENT,
  `employee_id` int NOT NULL,
  `employee_name` varchar(100) DEFAULT NULL,
  `department` varchar(100) DEFAULT NULL,
  `score` float DEFAULT '100',
  `task_score` float DEFAULT '0',
  `attendance_score` float DEFAULT '0',
  `tasks_accepted` int DEFAULT '0',
  `tasks_declined` int DEFAULT '0',
  `tasks_completed` int DEFAULT '0',
  `proofs_approved` int DEFAULT '0',
  `proofs_rejected` int DEFAULT '0',
  `days_present` int DEFAULT '0',
  `days_late` int DEFAULT '0',
  `days_absent` int DEFAULT '0',
  `last_updated` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `employee_id` (`employee_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `performance_scores`
--

LOCK TABLES `performance_scores` WRITE;
/*!40000 ALTER TABLE `performance_scores` DISABLE KEYS */;
INSERT INTO `performance_scores` VALUES (1,1,'Mohith','Development',85,0,0,0,0,0,0,1,0,0,0,'2026-03-20 20:06:03'),(2,2,'Uday','Cybersecurity',100,0,0,0,0,0,0,0,0,0,0,'2026-03-20 17:52:23');
/*!40000 ALTER TABLE `performance_scores` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `super_admin`
--

DROP TABLE IF EXISTS `super_admin`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `super_admin` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(200) NOT NULL,
  `password` varchar(200) NOT NULL,
  `name` varchar(100) DEFAULT 'Super Admin',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `super_admin`
--

LOCK TABLES `super_admin` WRITE;
/*!40000 ALTER TABLE `super_admin` DISABLE KEYS */;
INSERT INTO `super_admin` VALUES (1,'superadmin@gmail.com','super123','Super Admin','2026-03-13 16:53:10');
/*!40000 ALTER TABLE `super_admin` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tasks`
--

DROP TABLE IF EXISTS `tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `description` text,
  `assigned_to` int DEFAULT NULL,
  `assigned_by` varchar(100) DEFAULT 'Admin',
  `priority` enum('low','medium','high') DEFAULT 'medium',
  `status` enum('pending','accepted','in_progress','proof_submitted','completed','rejected','declined') DEFAULT 'pending',
  `due_date` date DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `accepted_at` datetime DEFAULT NULL,
  `proof_text` text,
  `proof_link` varchar(500) DEFAULT NULL,
  `proof_image` varchar(500) DEFAULT NULL,
  `proof_submitted_at` datetime DEFAULT NULL,
  `admin_verdict` enum('pending','approved','rejected') DEFAULT 'pending',
  `admin_note` varchar(500) DEFAULT NULL,
  `assigned_dept` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `assigned_to` (`assigned_to`),
  CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`assigned_to`) REFERENCES `employees` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tasks`
--

LOCK TABLES `tasks` WRITE;
/*!40000 ALTER TABLE `tasks` DISABLE KEYS */;
INSERT INTO `tasks` VALUES (2,'bugs','',1,'Admin','high','completed','2026-03-26','2026-03-12 12:51:21','2026-03-12 15:30:10',NULL,NULL,NULL,NULL,NULL,'pending',NULL,NULL),(3,'iuygg','iohugct',2,'Admin','high','pending','2026-03-12','2026-03-12 12:55:31','2026-03-12 12:55:31',NULL,NULL,NULL,NULL,NULL,'pending',NULL,NULL),(4,'jihugy','ihugyftf',1,'Admin','medium','completed','2026-03-13','2026-03-12 12:55:51','2026-03-12 15:30:06',NULL,NULL,NULL,NULL,NULL,'pending',NULL,NULL),(5,'ffghjk','importand',1,'Admin','high','completed','2026-03-28','2026-03-12 15:34:01','2026-03-12 15:34:51',NULL,NULL,NULL,NULL,NULL,'pending',NULL,NULL),(6,'fffff','ffffffff',1,'Admin','medium','completed','2026-03-14','2026-03-12 16:19:05','2026-03-12 16:21:21',NULL,'completed',NULL,NULL,'2026-03-12 21:50:27','approved','',NULL),(7,'meoifjwdnc','mkdjdfjend',1,'Admin','medium','completed','2026-03-20','2026-03-12 16:21:56','2026-03-12 16:28:05',NULL,NULL,NULL,'proof_uploads/proof_7_47b5f8cf.png','2026-03-12 21:55:42','approved','',NULL),(8,'aaaaaa','aaaa',1,'Admin','medium','completed','2026-03-20','2026-03-13 02:41:42','2026-03-13 02:43:48',NULL,'ckdn',NULL,'proof_uploads/proof_8_672dc5ee.png','2026-03-13 08:12:57','approved','',NULL),(9,'do this','ss',1,'Admin','medium','completed','2026-03-21','2026-03-13 09:23:28','2026-03-13 09:25:00',NULL,'sssss',NULL,'proof_uploads/proof_9_617a2140.png','2026-03-13 14:54:43','approved','',NULL),(10,'jjj','kkkkk',1,'Super Admin','high','completed','2026-03-10','2026-03-13 11:51:37','2026-03-13 12:12:19',NULL,NULL,NULL,'proof_uploads/proof_10_96f85988.pdf','2026-03-13 17:41:08','approved','',NULL),(11,'kkk','',1,'Super Admin','medium','in_progress','2026-03-18','2026-03-13 12:07:34','2026-03-20 14:04:59',NULL,NULL,NULL,'proof_uploads/proof_11_79174089.jpeg','2026-03-20 19:34:22','rejected','not sufficient','Development'),(12,'b','b',1,'Admin','high','in_progress','2026-03-28','2026-03-13 12:18:13','2026-03-20 14:04:52',NULL,NULL,NULL,'proof_uploads/proof_12_9e8516f1.jpg','2026-03-20 19:34:32','rejected','not suffient',NULL),(13,'ms','ns',1,'Admin','medium','completed','2026-03-28','2026-03-20 12:38:21','2026-03-20 12:39:07',NULL,NULL,NULL,'proof_uploads/proof_13_0dd67f61.jpeg','2026-03-20 18:09:00','approved','',NULL),(14,'ddcxc','xcxc',1,'Admin','high','completed','2026-03-21','2026-03-20 14:00:37','2026-03-20 14:03:23',NULL,NULL,NULL,'proof_uploads/proof_14_07d59593.jpg','2026-03-20 19:33:10','approved','',NULL),(15,'ssddsfd','dff',1,'Admin','medium','in_progress','2026-04-04','2026-03-20 14:03:55','2026-03-20 14:35:38',NULL,NULL,NULL,NULL,NULL,'pending',NULL,NULL),(16,'dddd','',1,'Admin','high','in_progress','2026-03-27','2026-03-20 14:35:20','2026-03-20 14:36:03',NULL,NULL,NULL,'proof_uploads/proof_16_daf9f9f8.jpeg','2026-03-20 20:05:55','rejected','jdffn',NULL);
/*!40000 ALTER TABLE `tasks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `work_logs`
--

DROP TABLE IF EXISTS `work_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `work_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `employee_id` int DEFAULT NULL,
  `log_date` date NOT NULL,
  `work_done` text NOT NULL,
  `hours_worked` decimal(4,2) DEFAULT '0.00',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `employee_id` (`employee_id`),
  CONSTRAINT `work_logs_ibfk_1` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `work_logs`
--

LOCK TABLES `work_logs` WRITE;
/*!40000 ALTER TABLE `work_logs` DISABLE KEYS */;
INSERT INTO `work_logs` VALUES (1,1,'2026-03-12','vhjlkuytrescvbhj',12.00,'2026-03-12 15:28:59'),(2,1,'2026-03-12','done the work',4.00,'2026-03-12 15:34:33');
/*!40000 ALTER TABLE `work_logs` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-20 21:03:38
