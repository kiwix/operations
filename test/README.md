# k8s test service

A simple web service to ensure k8s features are working properly:

- https://test.k8s.kiwix.org
- Uses a PVC matching a local-storage PV
- Uses an initer container (to set custom homepage inside volume)
- Uses an SSL certificate
- Uses an Ingress
- Uses Guaranteed QoS (set resources)
- Uses Node Affinity