---
layout: default
title: Publications
---

{% for pub in site.data.publications %}
- **{{ pub.title }}** ({{ pub.year }})  
  *{{ pub.venue }}*  
  [Link]({{ pub.link }})
{% endfor %}