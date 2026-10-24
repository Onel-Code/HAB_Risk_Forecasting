// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyAm9eqF6lrKfw2NdCPmeSsq0yqITh9abwQ",
  authDomain: "hab-risk-forecasting.firebaseapp.com",
  projectId: "hab-risk-forecasting",
  storageBucket: "hab-risk-forecasting.firebasestorage.app",
  messagingSenderId: "669743941785",
  appId: "1:669743941785:web:3b27a4dd9630322e2c9008"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

export const db = getFirestore(app);