check {
        writeLine("serverLog", "[METADATA] Start updating metadata.");
        iiBatchTransformVaultMetadata("0", *batch, *pause, *delay);
}

input *batch="256", *pause="0.5", *delay="60"
output ruleExecOut
