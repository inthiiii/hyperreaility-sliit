"""Raw extraction scoring against recognized fixture labels, before resolver fill-in."""
from project.agents.extraction import template_facts


def extraction_metrics(scenario, facts):
    expected=template_facts(scenario)
    def keys(values):
        return {(f.target_type,f.target_id,f.attribute,f.value,rid) for f in values for rid in f.evidence_ids}
    labels=keys(expected); predicted=keys(facts)
    labelled_reports={rid for *_,rid in labels}
    # Reports not recognized by the explicit fixture grammar have no labels here.
    scored={key for key in predicted if key[-1] in labelled_reports}
    tp=len(labels & scored);fp=len(scored-labels);fn=len(labels-scored)
    precision=tp/(tp+fp) if tp+fp else (1.0 if not labels else 0.0)
    recall=tp/(tp+fn) if tp+fn else None
    f1=2*precision*recall/(precision+recall) if recall is not None and precision+recall else (0.0 if labels else None)
    return {'label_source':'recognized fixture sentences, not hidden physical truth',
            'raw_model_output_only':True,'stage':'initial_extraction','labelled_reports':len(labelled_reports),
            'unlabelled_reports':len(scenario.reports)-len(labelled_reports),
            'true_positive':tp,'false_positive':fp,'false_negative':fn,
            'precision':precision if labels else None,'recall':recall,'f1':f1,
            'unlabelled_predictions':len(predicted-scored)}
