import { scenario_get_api } from "./tests/get-api.js";
import { scenario_post_api } from "./tests/post-api.js";
import { scenario_throttle } from "./tests/network-throttle-test.js";

export const options = {
  scenarios: {
    get_api: {
      executor: "shared-iterations",
      vus: 5,
      iterations: 10,
      exec: "scenario_get_api",
    },
    post_api: {
      executor: "shared-iterations",
      vus: 3,
      iterations: 6,
      exec: "scenario_post_api",
      startTime: "2s",
    },
    throttle: {
      executor: "shared-iterations",
      vus: 2,
      iterations: 4,
      exec: "scenario_throttle",
      startTime: "4s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1200"],
  },
};

// k6 a besoin que les fonctions soient visibles globalement via ce nom :
export { scenario_get_api, scenario_post_api, scenario_throttle };
