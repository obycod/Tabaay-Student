let subject = 'رياضيات ج2 \\ اول متوسط \\ علي صادق'; let safeName = subject.split('\\').join('-').split('/').join('-').split(':').join('-').trim(); console.log(safeName + '.png');
