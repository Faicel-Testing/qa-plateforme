import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 10,             // 🔹 100 utilisateurs virtuels
  duration: '5s',      // 🔹 Test sur 30 secondes
};

const url="https://gorest.co.in/public/v2/users/"
const payload = {
    "name": "Anshita",
    "job": "QA"
}

export default function () {
  const response=http.post(url,payload)
  console.log("*** printing payload ***",payload)
  console.log("*** printing response ***",response.body)
  check(response,{
  'status code validation':(response)=>response.status === 201,
  'Response Validation': (response) => response.body.includes('id')
  })
}